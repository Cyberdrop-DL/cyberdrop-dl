import dataclasses
import datetime
import functools
import logging
import random
import re
from enum import auto
from pathlib import Path
from typing import Annotated, ClassVar, Literal, Self, override

import aiohttp
from cyclopts import Parameter
from pydantic import (
    BaseModel,
    ByteSize,
    Field,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    PrivateAttr,
)

from cyberdrop_dl.constants import (
    DEFAULT_APP_STORAGE,
    DEFAULT_DOWNLOAD_STORAGE,
    LOGS_DATE_FORMAT,
    LOGS_DATETIME_FORMAT,
    CIStrEnum,
    HashMode,
)
from cyberdrop_dl.models import AliasModel, ConfigGroup
from cyberdrop_dl.models.types import (
    ByteSizeSerilized,
    CSVPath,
    FalsyAsNone,
    FalsyAsTuple,
    HttpURL,
    LogLevel,
    LogPath,
    NonEmptyStr,
    RemoveDuplicates,
    Timedelta,
)
from cyberdrop_dl.models.validators import strings


class _SubFoldersInclude(AliasModel):
    album_id: bool = False
    thread_id: bool = False
    domain: bool = True


class SubFolders(ConfigGroup, name=None):
    create: Annotated[bool, Parameter(name="--subfolders")] = True
    include: _SubFoldersInclude = Field(default_factory=_SubFoldersInclude)
    separate_posts_format: Annotated[
        NonEmptyStr, strings.format_validator({"default", "title", "id", "number", "date"})
    ] = "{default}"
    separate_posts: bool = False


class LogFiles(AliasModel):
    main: Annotated[LogPath, Parameter(alias="--log-file")] = Path("downloader.log")
    download_errors: CSVPath = Path("Download_Error_URLs.csv")
    scrape_errors: CSVPath = Path("Scrape_Error_URLs.csv")
    unsupported: CSVPath = Path("Unsupported_URLs.csv")

    @property
    def jsonl_file(self) -> Path:
        return self.main.with_suffix(".results.jsonl")


class Logs(ConfigGroup, name=None):  # noqa: PLW1641
    level: LogLevel = "DEBUG"
    "Only log messages of this level or higher to the main log file"
    console_level: FalsyAsNone[LogLevel] = None
    "Only log messages of this level or higher to the console. An empty or `None` value will use the same level as `log_level`"

    files: LogFiles = Field(default_factory=LogFiles)
    folder: Path = DEFAULT_APP_STORAGE / "Logs"
    expire_after: FalsyAsNone[Timedelta] = None
    rotate: bool = False
    _created_at: datetime.datetime = PrivateAttr(default_factory=datetime.datetime.now)

    @property
    def effective_level(self) -> int:
        return logging.getLevelNamesMapping()[self.level]

    @property
    def effective_console_level(self) -> int:
        if not self.console_level:
            return self.effective_level

        return logging.getLevelNamesMapping()[self.console_level]

    def resolve_filenames(self) -> None:
        self.folder = self.folder.expanduser().resolve().absolute()
        now_file_iso: str = self._created_at.strftime(LOGS_DATETIME_FORMAT)
        now_folder_iso: str = self._created_at.strftime(LOGS_DATE_FORMAT)

        def resolve(path: Path) -> Path:
            log_file = self.folder / path
            if self.rotate:
                file_name = f"{log_file.stem}_{now_file_iso}{log_file.suffix}"
                log_file = log_file.parent / now_folder_iso / file_name
            return log_file

        self.files = LogFiles.model_construct(
            None, **{name: resolve(value) for name, value in self.files.model_dump().items()}
        )

    def delete_old_logs_and_folders(self) -> None:
        if not self.expire_after:
            return

        for file in self.folder.rglob("*"):
            if file.suffix.lower() not in {".log", ".csv"}:
                continue

            if (self._created_at - datetime.datetime.fromtimestamp(file.stat().st_ctime)) > self.expire_after:  # noqa: DTZ006
                file.unlink()

    def __eq__(self, other: object) -> bool:
        # Exclude _created_at from compare (AKA __pydantic_private__)
        if not isinstance(other, BaseModel):
            return NotImplemented

        self_type = self.__pydantic_generic_metadata__["origin"] or self.__class__
        other_type = other.__pydantic_generic_metadata__["origin"] or other.__class__

        if not (self_type == other_type and self.__pydantic_extra__ == other.__pydantic_extra__):
            return False

        return self.__dict__ == other.__dict__


@dataclasses.dataclass(slots=True)
class _FloatRange:
    min: float
    max: float

    def __post_init__(self) -> None:
        if not self.max:
            self.max = float("inf")

    def __contains__(self, value: float, /) -> bool:
        return self.min <= value <= self.max

    @classmethod
    def parse(cls, min: float, max: float | None) -> Self | None:  # noqa: A002
        if not min and not max:
            return None
        return cls(min, max or float("inf"))


@dataclasses.dataclass(slots=True, frozen=True)
class _FileSizeRanges:
    video: _FloatRange
    image: _FloatRange
    audio: _FloatRange
    non_media: _FloatRange


class _SizeLimit(AliasModel):
    min: ByteSizeSerilized = ByteSize(0)
    max: ByteSizeSerilized = ByteSize(0)


@dataclasses.dataclass(slots=True, frozen=True)
class _MediaDurationRanges:
    video: _FloatRange | None
    audio: _FloatRange | None


class _DurationLimit(AliasModel):
    min: Timedelta = datetime.timedelta(seconds=0)
    max: Timedelta = datetime.timedelta(seconds=0)


@Parameter(name="*", name_transform=lambda name: name if name in {"min", "max"} else name + ".size")
class _FileSizes(AliasModel):
    image: _SizeLimit = Field(default_factory=_SizeLimit)
    video: _SizeLimit = Field(default_factory=_SizeLimit)
    audio: _SizeLimit = Field(default_factory=_SizeLimit)
    non_media: _SizeLimit = Field(default_factory=_SizeLimit)

    @functools.cached_property
    def ranges(self) -> _FileSizeRanges:
        return _FileSizeRanges(
            video=_FloatRange(
                self.video.min,
                self.video.max,
            ),
            image=_FloatRange(
                self.image.min,
                self.image.max,
            ),
            non_media=_FloatRange(
                self.non_media.min,
                self.non_media.max,
            ),
            audio=_FloatRange(
                self.audio.min,
                self.audio.max,
            ),
        )


@Parameter(name="*", name_transform=lambda name: name if name in {"min", "max"} else name + ".duration")
class _DurationLimits(AliasModel):
    video: _DurationLimit = Field(default_factory=_DurationLimit)
    audio: _DurationLimit = Field(default_factory=_DurationLimit)

    @property
    def needs_ffmpeg(self) -> bool:
        return bool(self.video.min or self.video.max or self.audio.min or self.audio.max)

    @functools.cached_property
    def ranges(self) -> _MediaDurationRanges:
        return _MediaDurationRanges(
            video=_FloatRange.parse(
                self.video.min.total_seconds(),
                self.video.max.total_seconds(),
            ),
            audio=_FloatRange.parse(
                self.audio.min.total_seconds(),
                self.audio.max.total_seconds(),
            ),
        )


@Parameter(name="*")
class _FileFilter(AliasModel):
    audio: bool = True
    images: bool = True
    videos: bool = True
    non_media: bool = True


class Filters(ConfigGroup):
    files: _FileFilter = Field(default_factory=_FileFilter)
    sizes: _FileSizes = Field(default_factory=_FileSizes)
    duration: _DurationLimits = Field(default_factory=_DurationLimits)
    before: FalsyAsNone[datetime.date] = None
    after: FalsyAsNone[datetime.date] = None
    filename_regex: FalsyAsNone[re.Pattern[str]] = None
    only_hosts: RemoveDuplicates[FalsyAsTuple[NonEmptyStr]] = ()
    skip_hosts: RemoveDuplicates[FalsyAsTuple[NonEmptyStr]] = ()
    allow_files_with_no_extension: bool = False


class Jdownloader(ConfigGroup, name=None):
    enabled: Annotated[bool, Parameter(name="--jdownloader")] = False
    autostart: bool = False
    download_dir: FalsyAsNone[Path] = None
    whitelist: RemoveDuplicates[FalsyAsTuple[NonEmptyStr]] = ()


class SortFormats(AliasModel):
    _COMMON_FIELDS: ClassVar[set[str]] = {
        "base_dir",
        "ext",
        "file_date",
        "file_date_iso",
        "file_date_us",
        "filename",
        "parent_dir",
        "sort_dir",
    }

    audio: Annotated[
        FalsyAsNone[NonEmptyStr],
        strings.format_validator(_COMMON_FIELDS | {"bitrate", "duration", "length", "sample_rate"}),
    ] = "{sort_dir}/{base_dir}/Audio/{filename}{ext}"
    "Format to generate sorted audio file"

    image: Annotated[
        FalsyAsNone[NonEmptyStr], strings.format_validator(_COMMON_FIELDS | {"height", "resolution", "width"})
    ] = "{sort_dir}/{base_dir}/Images/{filename}{ext}"
    "Format to generate sorted image file"

    non_media: Annotated[FalsyAsNone[NonEmptyStr], strings.format_validator(_COMMON_FIELDS)] = (
        "{sort_dir}/{base_dir}/Other/{filename}{ext}"
    )
    "Format to generate sorted files of unknown type"

    video: Annotated[
        FalsyAsNone[NonEmptyStr],
        strings.format_validator(
            _COMMON_FIELDS
            | {
                "codec",
                "duration",
                "fps",
                "height",
                "length",
                "resolution",
                "width",
            }
        ),
    ] = "{sort_dir}/{base_dir}/Videos/{filename}{ext}"
    "Format to generate sorted video file"

    incrementer: Annotated[NonEmptyStr, strings.format_validator({"i"})] = " ({i})"
    "Format for separator on name collisions"


class Sort(ConfigGroup, name=None):
    enabled: Annotated[bool, Parameter(name="--sort")] = False
    input_folder: FalsyAsNone[Path] = None
    output_folder: Path = DEFAULT_DOWNLOAD_STORAGE / "Cyberdrop-DL Sorted Downloads"
    formats: SortFormats = Field(default_factory=SortFormats)

    @property
    def needs_ffmpeg(self) -> bool:
        return bool(self.enabled and (self.formats.audio or self.formats.video))


class Dedupe(AliasModel):
    enabled: Annotated[bool, Parameter(name="--hashing.dedupe", alias="--auto-dedupe")] = True
    use_trash_bin: bool = True


class Hashing(ConfigGroup, name=None):
    mode: Annotated[HashMode, Parameter(name="--hashing")] = HashMode.IN_PLACE
    algorithms: Annotated[
        tuple[
            Annotated[
                Literal["xxh128", "md5", "sha256"],
                strings.pre_validator(to_lower=True, strip=True),
            ],
            ...,
        ],
        Parameter(alias="--hashes"),
    ] = (
        "xxh128",
        "md5",
        "sha256",
    )
    dedupe: Dedupe = Field(default_factory=Dedupe)
    _extra_hashes: tuple[Literal["md5", "sha256"], ...] = ()

    @override
    def model_post_init(self, *_) -> None:
        self.re_compute()

    def re_compute(self) -> None:
        hashes = set(self.algorithms)
        if (xxhash := "xxh128") not in hashes:
            self.algorithms = xxhash, *hashes
        hashes.discard(xxhash)
        self._extra_hashes = tuple(sorted(hashes))  # pyright: ignore[reportAttributeAccessIssue]

    @property
    def extra_hashes(self) -> tuple[Literal["md5", "sha256"], ...]:
        return self._extra_hashes


class Downloads(ConfigGroup):
    concurrency: Annotated[PositiveInt, Parameter(name="--downloads")] = 15
    concurrency_per_domain: Annotated[PositiveInt, Parameter(name="--downloads.per-domain")] = 5
    attempts: PositiveInt = 2
    delay: NonNegativeFloat = 0.0
    slow_speed: ByteSizeSerilized = ByteSize(0)
    speed_limit: ByteSizeSerilized = ByteSize(0)
    jitter: NonNegativeFloat = 0
    skip_and_mark_completed: bool = False
    concurrent_segments: PositiveInt = 10
    """Allow up to `<N>` HLS segments to be downloaded concurrently"""

    @property
    def total_delay(self) -> NonNegativeFloat:
        return self.delay + random.uniform(0, self.jitter)


class Network(ConfigGroup):
    dump_responses: bool = False
    """Save text/HTML/JSON responses to disk (flaresolverr responses are excluded)"""
    flaresolverr: FalsyAsNone[HttpURL] = None
    proxy: FalsyAsNone[HttpURL] = None
    rate_limit: PositiveFloat = 25
    connection_timeout: PositiveFloat = 15
    read_timeout: FalsyAsNone[PositiveFloat] = 300
    ssl_context: FalsyAsNone[
        Annotated[
            Literal["truststore", "certifi", "truststore+certifi"],
            strings.pre_validator(to_lower=True, strip=True),
        ]
    ] = "truststore+certifi"
    user_agent: NonEmptyStr = "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0"

    @property
    def curl_timeout(self) -> float | tuple[float, float]:
        if self.read_timeout is None:
            return self.connection_timeout
        return self.connection_timeout, self.read_timeout

    @property
    def aiohttp_timeout(self) -> aiohttp.ClientTimeout:
        return aiohttp.ClientTimeout(
            total=None,
            sock_connect=self.connection_timeout,
            sock_read=self.read_timeout,
        )


class UIMode(CIStrEnum):
    DISABLED = auto()
    ACTIVITY = auto()
    SIMPLE = auto()
    FULLSCREEN = auto()

    @property
    def is_disabled(self) -> bool:
        return self is UIMode.DISABLED

    @property
    def is_fullscreen(self) -> bool:
        return self is UIMode.FULLSCREEN


class UIOptions(ConfigGroup):
    mode: Annotated[UIMode, Parameter(name="--ui")] = UIMode.FULLSCREEN
    portrait: bool = False
    "force CDL to run with a vertical layout"
    refresh_rate: PositiveFloat = 10.0
