from __future__ import annotations

import datetime as dt
import time
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any, Literal, final

from cyclopts import Parameter
from typing_extensions import Sentinel

from cyberdrop_dl import __version__

if TYPE_CHECKING:
    from pathlib import Path

type ImpersonateTarget = Literal["chrome", "edge", "safari", "safari_ios", "chrome_android", "firefox"]

LOGS_DATETIME_FORMAT = "%Y%m%d_%H%M%S"
LOGS_DATE_FORMAT = "%Y_%m_%d"
START_TIME = time.monotonic()
STARTUP_TIME_STR = dt.datetime.now().strftime(LOGS_DATETIME_FORMAT)  # noqa: DTZ005
CDL_USER_AGENT = f"cyberdrop-dl/{__version__}"


MISSING: Any = Sentinel("MISSING")
HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "TRACE", "PATCH", "QUERY"]


DEFAULT_PARAMETER = Parameter(
    negative_iterable=[],
    json_dict=False,
    json_list=False,
    consume_multiple=True,
    allow_repeating=False,
)


class CIStrEnum(StrEnum):
    @classmethod
    def _missing_(cls, value: object) -> CIStrEnum | None:
        value = str(value).casefold()
        for member in cls:
            if member.name.casefold() == value:
                return member


class TempExt(StrEnum):
    HLS = ".cdl_hls"
    WRONG_CDL_HLS = ".cdl_hsl"  # used for a while in old versions, has a typo
    PART = ".part"

    def append_to[T: Path](self, path: T) -> T:
        return path.with_suffix(path.suffix + self)


BLOCKED_DOMAINS = frozenset(
    (
        "facebook",
        "instagram",
        "fbcdn",
        "gfycat",
        "ko-fi.com",
        "paypal.me",
        "amazon.com",
        "throne.com",
        "youtu.be",
        "youtube.com",
        "linktr.ee",
        "beacons.page",
        "beacons.ai",
        "allmylinks.com",
    )
)


class HashMode(CIStrEnum):
    OFF = auto()
    IN_PLACE = auto()
    POST_DOWNLOAD = auto()

    @property
    def enabled(self) -> bool:
        return self is not HashMode.OFF


@final
class FileExt:
    IMAGE = frozenset(
        {
            ".avif",
            ".bmp",
            ".gif",
            ".gifv",
            ".heic",
            ".heif",
            ".ico",
            ".jfif",
            ".jif",
            ".jpe",
            ".jpeg",
            ".jpg",
            ".jxl",
            ".png",
            ".svg",
            ".tif",
            ".tiff",
            ".webp",
        }
    )
    VIDEO = frozenset(
        {
            ".3gp",
            ".avchd",
            ".avi",
            ".f4v",
            ".flv",
            ".m2ts",
            ".m4p",
            ".m4v",
            ".mkv",
            ".mov",
            ".mp2",
            ".mp4",
            ".mpe",
            ".mpeg",
            ".mpeg1",
            ".mpeg2",
            ".mpeg4",
            ".mpg",
            ".mpv",
            ".mts",
            ".ogv",
            ".qt",
            ".swf",
            ".ts",
            ".vob",
            ".vp9",
            ".webm",
            ".wmv",
        }
    )
    AUDIO = frozenset(
        {
            ".aac",
            ".aiff",
            ".alac",
            ".dts",
            ".f4a",
            ".f4b",
            ".flac",
            ".m4a",
            ".mid",
            ".mka",
            ".mp3",
            ".mp4a",
            ".mpa",
            ".oga",
            ".ogg",
            ".vorbis",
            ".wav",
            ".weba",
        }
    )
    SUBTITLES = frozenset(
        {
            ".ass",
            ".srt",
            ".ssa",
            ".sub",
            ".vtt",
        }
    )
    TEXT = SUBTITLES | frozenset(
        {
            ".htm",
            ".html",
            ".md",
            ".nfo",
            ".txt",
        }
    )
    SEVEN_Z = frozenset(
        {
            ".7z",
            ".bz2",
            ".gz",
            ".tar",
            ".lzma",
            ".zip",
        }
    )
    VIDEO_OR_IMAGE = VIDEO | IMAGE
    MEDIA = AUDIO | VIDEO_OR_IMAGE
    DANGEROUS = frozenset(
        {
            ".bat",
            ".com",
            ".exe",
            ".hta",
            ".inf",
            ".jar",
            ".js",
            ".lnk",
            ".msc",
            ".msi",
            ".ps1",
            ".ps2",
            ".psc1",
            ".psc2",
            ".sh",
            ".scf",
            ".vb",
            ".vbs",
            ".wsc",
            ".wsh",
        }
    )
