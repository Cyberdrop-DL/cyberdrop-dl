from __future__ import annotations

from datetime import UTC, datetime
from enum import auto
from pathlib import Path
from typing import final

from rich.text import Text

from cyberdrop_dl import __version__, env
from cyberdrop_dl.compat import CIStrEnum, Enum, StrEnum

# TIME
STARTUP_TIME = datetime.now()
STARTUP_TIME_UTC = datetime.now(UTC)
LOGS_DATETIME_FORMAT = "%Y%m%d_%H%M%S"
LOGS_DATE_FORMAT = "%Y_%m_%d"
STARTUP_TIME_STR = STARTUP_TIME.strftime(LOGS_DATETIME_FORMAT)
CDL_USER_AGENT = f"cyberdrop-dl/{__version__}"


class TempExt(StrEnum):
    HLS = ".cdl_hls"
    WRONG_CDL_HLS = ".cdl_hsl"  # used for a while in old versions, has a typo
    PART = ".part"


class BlockedDomains:
    partial_match = (
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

    exact_match = ()

    if not env.ENABLE_TWITTER:
        partial_match = *partial_match, "twitter.com", ".x.com"
        exact_match = *exact_match, "x.com"


DEFAULT_APP_STORAGE = Path("./AppData")
DEFAULT_DOWNLOAD_STORAGE = Path("./Downloads")


class HashType(StrEnum):
    md5 = "md5"
    sha256 = "sha256"
    xxh128 = "xxh128"


class Hashing(CIStrEnum):
    OFF = auto()
    IN_PLACE = auto()
    POST_DOWNLOAD = auto()


class Browser(StrEnum):
    chrome = auto()
    firefox = auto()
    safari = auto()
    edge = auto()
    opera = auto()
    brave = auto()
    librewolf = auto()
    opera_gx = auto()
    vivaldi = auto()
    chromium = auto()


class NotificationResult(Enum):
    SUCCESS = Text("Success", "green")
    FAILED = Text("Failed", "bold red")
    PARTIAL = Text("Partial Success", "yellow")
    NONE = Text("No Notifications Sent", "yellow")


@final
class FileExt:
    IMAGE = frozenset(
        {
            ".gif",
            ".gifv",
            ".heic",
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
            ".mpg",
            ".mpv",
            ".mts",
            ".ogg",
            ".ogv",
            ".qt",
            ".swf",
            ".ts",
            ".webm",
            ".wmv",
        }
    )
    AUDIO = frozenset(
        {
            ".flac",
            ".m4a",
            ".mka",
            ".mp3",
            ".wav",
        }
    )
    TEXT = frozenset(
        {
            ".htm",
            ".html",
            ".md",
            ".nfo",
            ".txt",
            ".vtt",
            ".sub",
        }
    )
    SEVEN_Z = frozenset(
        {
            ".7z",
            ".bz2",
            ".gz",
            ".tar",
            ".zip",
        }
    )
    VIDEO_OR_IMAGE = VIDEO | IMAGE
    MEDIA = AUDIO | VIDEO_OR_IMAGE
