from __future__ import annotations

import asyncio
import dataclasses
import functools
import itertools
import json
import logging
import shutil
import subprocess
import uuid
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Self, TypeAlias, TypedDict, overload

from multidict import CIMultiDict, CIMultiDictProxy

from cyberdrop_dl.utils import DictDataclass

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Iterator, Mapping, Sequence

    from cyberdrop_dl.url_objects import AbsoluteHttpURL

    _CMD: TypeAlias = Iterable[str | Path]


logger = logging.getLogger(__name__)


class Args:
    CODEC_COPY = "-c", "copy"
    MAP_ALL_STREAMS = "-map", "0"
    CONCAT = "-f", "concat", "-safe", "0", "-i"
    FIXUP_MP4 = *MAP_ALL_STREAMS, "-ignore_unknown", *CODEC_COPY, "-f", "mp4", "-movflags", "+faststart"
    FIXUP_AUDIO_DTS_FILTER = "-bsf:a", "aac_adtstoasc"


_FFMPEG_CALL_PREFIX = "ffmpeg", "-y", "-loglevel", "error"
_FFPROBE_CALL_PREFIX = (
    "ffprobe",
    "-hide_banner",
    "-loglevel",
    "error",
    "-show_streams",
    "-show_format",
    "-print_format",
    "json",
)


def check_is_available() -> None:
    if not version():
        raise RuntimeError("ffmpeg is not installed")
    _check_ffprobe()


def _check_ffprobe() -> None:
    if not ffprobe_version():
        raise RuntimeError("ffprobe is not installed")


@functools.cache
def which_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


@functools.cache
def which_ffprobe() -> str | None:
    return shutil.which("ffprobe")


@functools.cache
def version() -> str | None:
    if bin_path := which_ffmpeg():
        return _get_bin_version(bin_path)


@functools.cache
def ffprobe_version() -> str | None:
    if bin_path := which_ffprobe():
        return _get_bin_version(bin_path)


async def merge(input_files: Iterable[Path], output_file: Path) -> SubProcessResult:
    result = await _merge(input_files, output_file)
    if result.success:
        await _delete_files(input_files, same_folder=False)
    return result


async def _merge(input_files: Iterable[Path], output_file: Path) -> SubProcessResult:
    inputs = itertools.chain.from_iterable(("-i", path) for path in input_files)
    command = *_FFMPEG_CALL_PREFIX, *inputs, *Args.MAP_ALL_STREAMS, *Args.CODEC_COPY, output_file
    return await _run_command(command)


async def concat(input_files: Iterable[Path], output_file: Path, *, same_folder: bool = True) -> SubProcessResult:
    concat_file = output_file.with_suffix(output_file.suffix + ".ffmpeg_concat.txt")
    await _create_concat_file(input_files, output_file=concat_file)
    try:
        result = await _concat(concat_file, output_file)
        if result.success:
            await _delete_files(input_files, same_folder=same_folder)
    finally:
        await _try_delete(concat_file)

    return result


async def _concat(input: Path, output: Path) -> SubProcessResult:
    concatenated_file = output.with_suffix(".concat" + output.suffix)
    command = *_FFMPEG_CALL_PREFIX, *Args.CONCAT, input, *Args.CODEC_COPY, concatenated_file
    result = await _run_command(command)
    if not result.success:
        return result
    return await _fixup_concat_video(concatenated_file, output)


async def _create_concat_file(input_files: Iterable[Path], output_file: Path) -> None:
    # Input paths MUST be absolute!!.

    def write() -> None:
        with output_file.open("w", encoding="utf8") as f:
            f.writelines(f"file '{file}'\n" for file in input_files)

    return await asyncio.to_thread(write)


async def _fixup_concat_video(input_file: Path, output_file: Path) -> SubProcessResult:
    command = *_FFMPEG_CALL_PREFIX, "-i", input_file, *Args.FIXUP_MP4
    probe_result = await probe(input_file)
    if probe_result and (audio := probe_result.audio) and audio.codec == "aac":
        command = *command, *Args.FIXUP_AUDIO_DTS_FILTER
    command = *command, output_file
    result = await _run_command(command)
    if result.success:
        await _try_delete(input_file)
    return result


async def _try_delete(file: Path) -> None:
    try:
        await asyncio.to_thread(file.unlink, missing_ok=True)
    except OSError as e:
        logger.warning(f"Unable to delete '{file}' {e}")


async def _delete_files(files: Iterable[Path], *, same_folder: bool) -> None:
    if same_folder:
        folder = next(iter(files)).parent
        logger.debug("Deleting all files inside '%s'", folder)
        await asyncio.to_thread(shutil.rmtree, folder, ignore_errors=True)
    else:
        _ = await asyncio.gather(*map(_try_delete, files))


async def merge_subs(files: Iterable[Path], output: Path) -> None:
    logger.debug("Merging subs to '%s'", output)
    await asyncio.to_thread(_raw_concat, files, output)


def _raw_concat(files: Iterable[Path], output: Path) -> None:
    with output.open("wb") as out:
        for file in files:
            with file.open("rb") as fp_in:
                out.write(fp_in.read())

            file.unlink()


@overload
async def probe(input: Path, /) -> FFprobeResult: ...


@overload
async def probe(input: AbsoluteHttpURL, /, *, headers: Mapping[str, str] | None = None) -> FFprobeResult: ...


async def probe(input: Path | AbsoluteHttpURL, /, *, headers: Mapping[str, str] | None = None) -> FFprobeResult:
    _check_ffprobe()

    if isinstance(input, Path):
        assert input.is_absolute()
        assert not headers

    command = *_FFPROBE_CALL_PREFIX, str(input)
    if headers:
        command = (
            *command,
            *itertools.chain.from_iterable(("-headers", f"{name}: {value}") for name, value in headers.items()),
        )
    result = await _run_command(command)
    if not result.success:
        return _EMPTY_FFPROBE_RESULT
    return FFprobeResult.from_output(json.loads(result.stdout))


def _get_bin_version(bin_path: str) -> str | None:
    try:
        stdout = subprocess.run(
            (bin_path, "-version"),
            timeout=5,
            check=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ).stdout.decode("utf-8", errors="ignore")

    except Exception:
        return
    else:
        return stdout.partition("version")[-1].partition("Copyright")[0].strip()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~ FFprobe ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def _parse_duration(duration: str | float | None) -> TruncatedFloat | None:
    if not duration:
        return None

    if isinstance(duration, (float, int)):
        seconds: float | int = duration

    else:
        try:
            *rest, seconds_str = duration.strip().split(":")

            seconds = float(seconds_str)
            for idx, value in enumerate(reversed(rest), 1):
                seconds += int(value) * 60**idx

        except Exception:
            return None

    if seconds > 0:
        return TruncatedFloat(seconds)


class FFprobeOutput(TypedDict):
    streams: list[dict[str, Any]]


class Tags(CIMultiDictProxy[Any]): ...


class TruncatedFloat(float):
    def __str__(self) -> str:
        return str(int(self)) if self.is_integer() else f"{self:.2f}"


@dataclasses.dataclass(slots=True, kw_only=True)
class Stream(DictDataclass):
    index: int
    codec: str
    codec_type: str
    bitrate: int | None
    duration: TruncatedFloat | None
    tags: Tags

    @classmethod
    def validate(cls, stream_info: dict[str, Any]) -> dict[str, Any]:
        info = cls.filter_dict(stream_info)
        tags = Tags(CIMultiDict(stream_info.get("tags", {})))
        return info | {
            "codec": stream_info.get("codec_name"),
            "duration": _parse_duration(stream_info.get("duration") or tags.get("duration")),
            "bitrate": int(stream_info.get("bitrate") or stream_info.get("bit_rate") or 0) or None,
            "tags": tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], /, **overrides: Any) -> Self:
        return cls(**cls.validate(data))


@dataclasses.dataclass(slots=True, kw_only=True)
class AudioStream(Stream):
    sample_rate: int | None
    codec_type: Literal["audio"] = "audio"  # pyright: ignore[reportIncompatibleVariableOverride]

    @classmethod
    def validate(cls, stream_info: dict[str, Any]) -> dict[str, Any]:
        defaults = super(AudioStream, cls).validate(stream_info)
        sample_rate = int(float(stream_info.get("sample_rate", 0))) or None
        return defaults | {"sample_rate": sample_rate}


@dataclasses.dataclass(slots=True, kw_only=True)
class VideoStream(Stream):
    width: int | None
    height: int | None
    fps: TruncatedFloat | None
    resolution: str | None
    codec_type: Literal["video"] = "video"  # pyright: ignore[reportIncompatibleVariableOverride]

    @classmethod
    def validate(cls, stream_info: dict[str, Any]) -> dict[str, Any]:
        width = int(float(stream_info.get("width", 0))) or None
        height = int(float(stream_info.get("height", 0))) or None
        resolution = fps = None
        if width and height:
            resolution: str | None = f"{width}x{height}"

        if (avg_fps := stream_info.get("avg_frame_rate")) and str(avg_fps) not in ("0/0", "0", "0.0"):
            fps: TruncatedFloat | None = TruncatedFloat(Fraction(avg_fps))

        defaults = super(VideoStream, cls).validate(stream_info)
        return defaults | {"width": width, "height": height, "fps": fps, "resolution": resolution}


@dataclasses.dataclass(slots=True)
class Format:
    size: int | None
    bitrate: int | None
    duration: TruncatedFloat | None
    tags: Tags

    @classmethod
    def from_dict(cls, format_info: dict[str, Any]) -> Self:
        tags = Tags(CIMultiDict(format_info.get("tags", {})))

        return cls(
            size=int(float(format_info.get("size") or 0)) or None,
            duration=_parse_duration(format_info.get("duration") or tags.get("duration")),
            bitrate=int(format_info.get("bitrate") or format_info.get("bit_rate") or 0) or None,
            tags=tags,
        )


@dataclasses.dataclass(slots=True)
class FFprobeResult:
    ffprobe_output: FFprobeOutput
    streams: tuple[VideoStream | AudioStream, ...]
    format: Format

    audio: AudioStream | None = dataclasses.field(init=False)
    """First audio stream"""
    video: VideoStream | None = dataclasses.field(init=False)
    """First video stream"""

    def __post_init__(self) -> None:
        self.audio = next(self.audio_streams(), None)
        self.video = next(self.video_streams(), None)

    def __bool__(self) -> bool:
        return bool(self.streams)

    def __iter__(self) -> Iterator[Stream]:
        return iter(self.streams)

    @staticmethod
    def from_output(ffprobe_output: FFprobeOutput) -> FFprobeResult:
        def streams():
            for stream in ffprobe_output.get("streams", ()):
                match stream["codec_type"]:
                    case "video":
                        yield VideoStream.from_dict(stream)
                    case "audio":
                        yield AudioStream.from_dict(stream)
                    case _:
                        pass

        return FFprobeResult(
            ffprobe_output,
            streams=tuple(streams()),
            format=Format.from_dict(ffprobe_output.get("format", {})),
        )

    def video_streams(self) -> Generator[VideoStream]:
        for stream in self.streams:
            if stream.codec_type == "video":
                yield stream

    def audio_streams(self) -> Generator[AudioStream]:
        for stream in self.streams:
            if stream.codec_type == "audio":
                yield stream


_EMPTY_FFPROBE_RESULT: FFprobeResult = FFprobeResult.from_output({"streams": []})

# ~~~~~~~~~~~~~~~~~~~~~~ Subprocess ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


@dataclasses.dataclass(slots=True)
class SubProcessResult:
    stdout: str
    stderr: str
    return_code: int | None
    success: bool = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self.success = self.return_code == 0

    def __json__(self) -> dict[str, Any]:
        me = dataclasses.asdict(self)
        try:
            stdout = json.loads(self.stdout)
        except json.JSONDecodeError:
            pass
        else:
            me["stdout"] = stdout
        return me

    def __str__(self) -> str:
        return str(self.__json__())


async def _run_command(command: Sequence[str | Path]) -> SubProcessResult:
    assert not isinstance(command, str)
    program, *cmd = command

    if program == "ffmpeg":
        bin = which_ffmpeg()
    elif program == "ffprobe":
        bin = which_ffprobe()
    else:
        raise ValueError(f"Unexpected program in command {command}")

    assert bin
    process_id = str(uuid.uuid4())
    logger.debug("Running %s subprocess [id=%s]\n:%s", program, process_id, {"command": [bin, *cmd]})
    process = await asyncio.create_subprocess_exec(bin, *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    result = SubProcessResult(
        stdout=stdout.decode("utf-8", errors="ignore"),
        stderr=stderr.decode("utf-8", errors="ignore"),
        return_code=process.returncode,
    )
    logger.debug("%s subprocess [id=%s] output:\n%s", program, process_id, result)
    return result
