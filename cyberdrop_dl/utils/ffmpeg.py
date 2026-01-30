from __future__ import annotations

import asyncio
import functools
import itertools
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, Required, Self, TypeAlias, TypedDict, overload

import aiofiles
import aiofiles.os
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

from cyberdrop_dl.utils.logger import log_debug
from cyberdrop_dl.utils.utilities import get_valid_dict, is_absolute_http_url

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping, Sequence

    from cyberdrop_dl.data_structures import AbsoluteHttpURL

    _CMD: TypeAlias = Sequence[str | Path]


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
_EMPTY_FFPROBE_OUTPUT: FFprobeOutput = {"streams": []}


def check_is_available() -> None:
    if not get_ffmpeg_version():
        raise RuntimeError("ffmpeg is not available")
    _check_ffprobe()


def _check_ffprobe():
    if not get_ffprobe_version():
        raise RuntimeError("ffprobe is not available")


@functools.cache
def which_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


@functools.cache
def which_ffprobe() -> str | None:
    return shutil.which("ffprobe")


@functools.cache
def get_ffmpeg_version() -> str | None:
    if bin_path := which_ffmpeg():
        return _get_bin_version(bin_path)


@functools.cache
def get_ffprobe_version() -> str | None:
    if bin_path := which_ffprobe():
        return _get_bin_version(bin_path)


async def concat(input_files: Sequence[Path], output_file: Path, *, same_folder: bool = True) -> SubProcessResult:
    concat_file_path = output_file.with_suffix(output_file.suffix + ".ffmpeg_concat.txt")
    await _create_concat_input_file(input_files, output_file=concat_file_path)
    result = await _concat(concat_file_path, output_file)
    if result.success:
        if same_folder:
            folder = input_files[0].parent
            await asyncio.to_thread(shutil.rmtree, folder, ignore_errors=True)
        else:
            await _async_delete_files(input_files)

    await asyncio.to_thread(concat_file_path.unlink)
    return result


async def merge(input_files: Sequence[Path], output_file: Path) -> SubProcessResult:
    result = await _merge(input_files, output_file=output_file)
    if result.success:
        await _async_delete_files(input_files)
    return result


@overload
async def probe(input: Path, /) -> FFprobeResult: ...


@overload
async def probe(input: AbsoluteHttpURL, /, *, headers: Mapping[str, str] | None = None) -> FFprobeResult: ...


async def probe(input: Path | AbsoluteHttpURL, /, *, headers: Mapping[str, str] | None = None) -> FFprobeResult:
    _check_ffprobe()
    if isinstance(input, URL):
        assert is_absolute_http_url(input)

    elif isinstance(input, Path):
        assert input.is_absolute()
        assert not headers

    else:
        raise ValueError("Can only probe a Path or a yarl.URL")

    command = *_FFPROBE_CALL_PREFIX, str(input)
    if headers:
        headers_cmd = itertools.chain.from_iterable(("-headers", f"{name}: {value}") for name, value in headers.items())
        command = *command, *headers_cmd
    result = await _run_command(command)
    output = json.loads(result.stdout) if result.success else _EMPTY_FFPROBE_OUTPUT
    return FFprobeResult.from_output(output)


async def _async_delete_files(files: Sequence[Path]) -> None:
    await asyncio.gather(*[aiofiles.os.unlink(file) for file in files])


async def _create_concat_input_file(input_files: Sequence[Path], output_file: Path) -> None:
    """Input paths MUST be absolute!!."""
    async with aiofiles.open(output_file, "w", encoding="utf8") as f:
        await f.writelines(f"file '{file}'\n" for file in input_files)


async def _fixup_concatenated_video_file(input_file: Path, output_file: Path) -> SubProcessResult:
    command = *_FFMPEG_CALL_PREFIX, "-i", input_file, *Args.FIXUP_MP4
    probe_result = await probe(input_file)
    if probe_result and (audio := probe_result.audio) and audio.codec == "aac":
        command += Args.FIXUP_AUDIO_DTS_FILTER
    command = *command, output_file
    result = await _run_command(command)
    if result.success:
        await asyncio.to_thread(input_file.unlink)
    return result


async def _concat(concat_input_file: Path, output_file: Path) -> SubProcessResult:
    concatenated_file = output_file.with_suffix(".concat" + output_file.suffix)
    command = *_FFMPEG_CALL_PREFIX, *Args.CONCAT, concat_input_file, *Args.CODEC_COPY, concatenated_file
    result = await _run_command(command)
    if not result.success:
        return result
    return await _fixup_concatenated_video_file(concatenated_file, output_file)


async def _merge(input_files: Sequence[Path], output_file: Path) -> SubProcessResult:
    inputs = itertools.chain.from_iterable(("-i", path) for path in input_files)
    command = *_FFMPEG_CALL_PREFIX, *inputs, *Args.MAP_ALL_STREAMS, *Args.CODEC_COPY, output_file
    return await _run_command(command)


def _get_bin_version(bin_path: str) -> str | None:
    try:
        cmd = bin_path, "-version"
        p = subprocess.run(
            cmd, timeout=5, check=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        stdout = p.stdout.decode("utf-8", errors="ignore")
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired, OSError, ValueError):
        return
    else:
        return stdout.partition("version")[-1].partition("Copyright")[0].strip()


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~ FFprobe ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def _parse_duration(duration: str | float | None) -> TruncatedFloat | None:
    if not duration:
        return None

    if isinstance(duration, (float, int)):
        seconds = duration

    else:
        try:
            *rest, seconds = duration.strip().split(":")

            seconds = float(seconds)
            for idx, value in enumerate(reversed(rest), 1):
                seconds += int(value) * 60**idx
        except Exception:
            return None

    if seconds > 0:
        return TruncatedFloat(seconds)


class StreamDict(TypedDict, total=False):
    index: Required[int]
    codec_type: Required[Literal["video", "audio", "subtitle"]]


class FFprobeOutput(TypedDict, total=False):
    streams: Required[list[StreamDict]]


class Tags(CIMultiDictProxy[Any]): ...


class TruncatedFloat(float):
    def __str__(self) -> str:
        return str(int(self)) if self.is_integer() else f"{self:.2f}"


@dataclass(frozen=True, slots=True, kw_only=True)
class Stream:
    index: int
    codec: str
    codec_type: str
    bitrate: int | None
    duration: TruncatedFloat | None
    tags: Tags

    @classmethod
    def validate(cls, stream_info: StreamDict) -> dict[str, Any]:
        info = get_valid_dict(cls, stream_info)
        tags = Tags(CIMultiDict(stream_info.get("tags", {})))
        return info | {
            "codec": stream_info.get("codec_name"),
            "duration": _parse_duration(stream_info.get("duration") or tags.get("duration")),
            "bitrate": int(stream_info.get("bitrate") or stream_info.get("bit_rate") or 0) or None,
            "tags": tags,
        }

    @classmethod
    def from_dict(cls, stream_info: StreamDict) -> Self:
        return cls(**cls.validate(stream_info))

    def as_jsonable_dict(self) -> dict[str, Any]:
        return asdict(self) | {"tags": dict(self.tags)}


@dataclass(frozen=True, slots=True, kw_only=True)
class AudioStream(Stream):
    sample_rate: int | None
    codec_type: Literal["audio"] = "audio"

    @classmethod
    def validate(cls, stream_info: StreamDict) -> dict[str, Any]:
        defaults = super(AudioStream, cls).validate(stream_info)
        sample_rate = int(float(stream_info.get("sample_rate", 0))) or None
        return defaults | {"sample_rate": sample_rate}


@dataclass(frozen=True, slots=True, kw_only=True)
class VideoStream(Stream):
    width: int | None
    height: int | None
    fps: TruncatedFloat | None
    resolution: str | None
    codec_type: Literal["video"] = "video"

    @classmethod
    def validate(cls, stream_info: StreamDict) -> dict[str, Any]:
        width = int(float(stream_info.get("width", 0))) or None
        height = int(float(stream_info.get("height", 0))) or None
        resolution = fps = None
        if width and height:
            resolution: str | None = f"{width}x{height}"

        if (avg_fps := stream_info.get("avg_frame_rate")) and str(avg_fps) not in {"0/0", "0", "0.0"}:
            fps: TruncatedFloat | None = TruncatedFloat(Fraction(avg_fps))

        defaults = super(VideoStream, cls).validate(stream_info)
        return defaults | {"width": width, "height": height, "fps": fps, "resolution": resolution}


@dataclass(frozen=True, slots=True, kw_only=True)
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


@dataclass(frozen=True, slots=True)
class FFprobeResult:
    ffprobe_output: FFprobeOutput
    streams: tuple[Stream, ...]
    format: Format

    @staticmethod
    def from_output(ffprobe_output: FFprobeOutput) -> FFprobeResult:
        def streams():
            for stream in ffprobe_output.get("streams", []):
                if stream["codec_type"] == "video":
                    yield VideoStream.from_dict(stream)
                elif stream["codec_type"] == "audio":
                    yield AudioStream.from_dict(stream)

        return FFprobeResult(
            ffprobe_output,
            streams=tuple(streams()),
            format=Format.from_dict(ffprobe_output.get("format", {})),
        )

    def video_streams(self) -> Generator[VideoStream]:
        for stream in self.streams:
            if isinstance(stream, VideoStream):
                yield stream

    def audio_streams(self) -> Generator[AudioStream]:
        for stream in self.streams:
            if isinstance(stream, AudioStream):
                yield stream

    @property
    def audio(self) -> AudioStream | None:
        """First audio stream"""
        return next(self.audio_streams(), None)

    @property
    def video(self) -> VideoStream | None:
        """First video stream"""
        return next(self.video_streams(), None)

    def __bool__(self) -> bool:
        return bool(self.ffprobe_output.get("streams"))


# ~~~~~~~~~~~~~~~~~~~~~~ Subprocess ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class SubProcessResult(NamedTuple):
    return_code: int | None
    stdout: str
    stderr: str
    success: bool
    command: _CMD

    def as_jsonable_dict(self) -> dict[str, Any]:
        joined_command = " ".join(map(str, self.command))
        return self._asdict() | {"command": joined_command}


async def _run_command(command: _CMD) -> SubProcessResult:
    assert not isinstance(command, str)
    bin_path, cmd = command[0], command[1:]
    if bin_path == "ffmpeg":
        bin_path = which_ffmpeg()
    elif bin_path == "ffprobe":
        bin_path = which_ffprobe()
    assert bin_path
    command_ = bin_path, *cmd
    log_debug(f"Running command: {command_}")
    process = await asyncio.create_subprocess_exec(*command_, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    return_code = process.returncode
    stdout_str = stdout.decode("utf-8", errors="ignore")
    stderr_str = stderr.decode("utf-8", errors="ignore")
    results = SubProcessResult(return_code, stdout_str, stderr_str, return_code == 0, command_)
    log_debug(results.as_jsonable_dict())
    return results
