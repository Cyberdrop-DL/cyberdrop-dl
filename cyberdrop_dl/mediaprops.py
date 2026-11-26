from __future__ import annotations

import dataclasses
import logging
import re
from fractions import Fraction
from typing import TYPE_CHECKING, Any, ClassVar, Final, NamedTuple, final

from cyberdrop_dl.exceptions import ScrapeError

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Mapping

    import yarl

    from cyberdrop_dl.url_objects import AbsoluteHttpURL

logger = logging.getLogger(__name__)

VIDEO_CODECS = (
    "av1",
    "avc1",
    "avc2",
    "avc3",
    "avc4",
    "dvh1",
    "dvhe",
    "h263",
    "h264",
    "hevc",
    "hevc1",
    "hevc2",
    "hev1",
    "hev2",
    "hvc1",
    "hvc2",
    "mp4v",
    "theora",
    "vp8",
    "vp9",
    "vp10",
)
AUDIO_CODECS = (
    "aac",
    "ac-3",
    "ac-4",
    "dtsc",
    "dtse",
    "dtsh",
    "dtsl",
    "eac3",
    "ec-3",
    "flac",
    "mp3",
    "mp4a",
    "opus",
    "vorbis",
)
SUB_CODECS = "stpp", "wvtt"


@final
@dataclasses.dataclass(slots=True, frozen=True)
class Codecs:
    video: str | None = None
    audio: str | None = None
    subs: str | None = None
    hdr: str | None = None

    UNKNOWN: ClassVar[Codecs]

    @staticmethod
    def _parse_hdr(v_codec_parts: list[str]) -> str | None:
        match v_codec_parts:
            case ["av1", _, _, "10", *_] | ["vp9", "2", *_]:
                return "HDR10"
            case [name, *_] if name in ("dvh1", "dvhe"):
                return "DV"
            case _:
                return None

    @staticmethod
    def split(codecs: str) -> Generator[str]:
        for codec in map(str.strip, codecs.strip().strip(",").split(",")):
            if codec:
                yield re.sub(r"^([^.]+)", lambda c: c.group(1).lower(), codec)

    @staticmethod
    def normalize(codec: str) -> str:
        return re.sub(r"0+(?=\d)", "", codec)

    @staticmethod
    def pretty_name(codec: str) -> str:
        name = Codecs.normalize(codec).partition(".")[0]
        for pf in ("hevc1", "hev1", "hvc1", "hevc", "hev", "hvc"):
            if name.startswith(pf):
                return name.replace(pf, "hevc")
        return name

    @staticmethod
    def parse(codecs: str) -> Codecs:
        codecs = codecs.strip()
        if not codecs:
            return Codecs.UNKNOWN

        v_codec = a_codec = s_codec = hdr = None
        codecs_tuple = tuple(Codecs.split(codecs))
        for codec in codecs_tuple:
            parts = Codecs.normalize(codec).split(".")
            name = parts[0]
            if name in AUDIO_CODECS:
                a_codec = a_codec or codec
            elif name in VIDEO_CODECS:
                if not v_codec:
                    v_codec = codec
                    hdr = Codecs._parse_hdr(parts)
            elif name in SUB_CODECS:
                s_codec = s_codec or codec
            else:
                logger.warning("Unknown RFC6381 codec: %s", codec)

        if v_codec or a_codec or s_codec:
            return Codecs(v_codec, a_codec, s_codec, hdr)

        if len(codecs_tuple) == 2:
            return Codecs(*codecs_tuple)

        return Codecs.UNKNOWN


Codecs.UNKNOWN = Codecs()


@final
class Resolution(NamedTuple):
    width: int
    height: int

    @staticmethod
    def from_dict(res: Mapping[str, Any]) -> Resolution:
        return Resolution(**{key: res[key] for key in Resolution._fields})

    @property
    def name(self) -> str:
        if 7600 < self.width < 8200:
            return "8K"
        if 3800 < self.width < 4100:
            return "4K"
        return f"{self.height}p"

    @property
    def aspect_ratio(self) -> Fraction:
        return Fraction(self.width, self.height)

    @staticmethod
    def parse(url_number_or_string: yarl.URL | str | int | None, /) -> Resolution:  # noqa: PLR0911
        if url_number_or_string is None:
            return UNKNOWN_RESOLUTION

        if isinstance(url_number_or_string, int):
            return Resolution._from_height(url_number_or_string)

        if not isinstance(url_number_or_string, str):
            for resolution in COMMON_RESOLUTIONS:
                if str(resolution.height) in url_number_or_string.parts:
                    return resolution

            url_number_or_string = url_number_or_string.path

        # "1080p", "720i", "480P", the most common case
        if (height := url_number_or_string.rstrip("pPiI")).isdecimal():
            return Resolution._from_height(height)

        # "1920x1080", "1280X720" or "640,480"
        if match := re.search(r"(?P<width>\d+)[xX,](?P<height>\d+)", url_number_or_string):
            return Resolution(
                width=int(match.group("width")),
                height=int(match.group("height")),
            )

        #  "1080p", "720i", "480P" w regex, slower but works with substrings
        if match := re.search(r"(?<![a-zA-Z0-9])(\d+)[pPiI](?![a-zA-Z0-9])", url_number_or_string):
            return Resolution._from_height(match.group(1))

        # "2K", "4K", "8K"
        if match := re.search(r"\b([248])[kK]\b", url_number_or_string):
            height = {"2": 1440, "4": 2160, "8": 4320}[match.group(1)]
            return Resolution._from_height(height)

        raise ValueError(f"Unable to parse resolution from {url_number_or_string}")

    @staticmethod
    def _from_height(height: str | int, aspect_ratio: float = 16 / 9) -> Resolution:
        height = int(height)
        width = round(height * aspect_ratio)
        return Resolution(width, height)

    @staticmethod
    def unknown() -> Resolution:
        return UNKNOWN_RESOLUTION

    @staticmethod
    def highest() -> Resolution:
        return HIGHEST_RESOLUTION

    @staticmethod
    def make_parser() -> Callable[[yarl.URL | str | int | None], Resolution]:
        """Returns a callable wrapper around `Resolution.parse` that can return `Resolution.unknown()`

        Raises `ScrapeError` if more that 1 unknown resolution is parsed"""

        default_res: Resolution | None = None

        def parse(quality: yarl.URL | str | int | None, /) -> Resolution:
            nonlocal default_res
            try:
                return Resolution.parse(quality)
            except ValueError as e:
                if default_res is not None:
                    msg = "Unable to select best quality. Resource has more that 1 unknown resolution"
                    raise ScrapeError(422, msg) from e

                default_res = Resolution.unknown()
                return default_res

        return parse


UNKNOWN_RESOLUTION = Resolution.parse(0)
HIGHEST_RESOLUTION = Resolution(9999, 9999)


COMMON_RESOLUTIONS: Final = tuple(
    Resolution(*resolution)  # Best to worst
    for resolution in (
        (7680, 4320),
        (3840, 2160),
        (2560, 1440),
        (1920, 1080),
        (1280, 720),
        (640, 480),
        (640, 360),
        (480, 320),
        (426, 240),
        (320, 240),
        (256, 144),
    )
)


@dataclasses.dataclass(slots=True, kw_only=True, frozen=True)
class ISO639Subtitle:
    """`lang_code` MUST be a valid ISO639 code (ex: en, eng, fra)"""

    url: AbsoluteHttpURL | str
    lang_code: str
    name: str | None = None
    ext: str | None = None
    fallback_ext: str | None = None


@final
@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class ResolvedISO639Subtitle:
    url: AbsoluteHttpURL
    lang_code: str
    ext: str | None
    name: str | None = None
