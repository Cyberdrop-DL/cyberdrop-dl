# ruff: noqa: RUF012
import dataclasses
import datetime
import functools
import logging
import random
import re
from collections.abc import Callable
from enum import auto
from pathlib import Path
from typing import Annotated, Any, ClassVar, Literal, Self, override

import aiohttp
from cyclopts import Parameter
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ByteSize,
    Field,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    PrivateAttr,
    field_validator,
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
    HttpURL,
    ListNonEmptyStr,
    ListPydanticURL,
    LogPath,
    MainLogPath,
    NonEmptyStr,
    NonEmptyStrOrNone,
    PathOrNone,
)
from cyberdrop_dl.models.validators import falsy_as, falsy_as_none, to_timedelta
from cyberdrop_dl.utils.strings import validate_format_string


def _format_validator(valid_keys: set[str]) -> Callable[[str | None], str | None]:

    def check(value: str | None) -> str | None:
        if value is not None:
            validate_format_string(value, valid_keys)
        return value

    return check


class SubFoldersInclude(AliasModel):
    album_id: bool = False
    thread_id: bool = False
    domain: bool = True


class SubFolders(ConfigGroup, name=None):
    create: Annotated[bool, Parameter(name="--subfolders")] = True
    include: SubFoldersInclude = Field(default_factory=SubFoldersInclude)
    separate_posts_format: Annotated[
        NonEmptyStr, AfterValidator(_format_validator({"default", "title", "id", "number", "date"}))
    ] = "{default}"
    separate_posts: bool = False


class LogFiles(AliasModel):
    main: Annotated[MainLogPath, Parameter(alias="--log-file")] = Path("downloader.log")
    download_errors: LogPath = Path("Download_Error_URLs.csv")
    scrape_errors: LogPath = Path("Scrape_Error_URLs.csv")
    unsupported: LogPath = Path("Unsupported_URLs.csv")

    @property
    def jsonl_file(self) -> Path:
        return self.main.with_suffix(".results.jsonl")


class Logs(ConfigGroup, name=None):  # noqa: PLW1641
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"
    "Only log messages of this level or higher to the main log file"
    console_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None = None
    "Only log messages of this level or higher to the console. An empty or `None` value will use the same level as `log_level`"

    files: LogFiles = Field(default_factory=LogFiles)
    folder: Path = DEFAULT_APP_STORAGE / "Logs"
    expire_after: datetime.timedelta | None = None
    rotate: bool = False
    _created_at: datetime.datetime = PrivateAttr(default_factory=datetime.datetime.now)

    @field_validator("level", "console_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> Any:
        value = falsy_as_none(value)
        if type(value) is str:
            return value.upper()
        return value

    @property
    def effective_level(self) -> int:
        return logging.getLevelNamesMapping()[self.level]

    @property
    def effective_console_level(self) -> int:
        if not self.console_level:
            return self.effective_level

        return logging.getLevelNamesMapping()[self.console_level]

    @field_validator("expire_after", mode="before")
    @staticmethod
    def _parse_logs_duration(input_date: datetime.timedelta | str | int | None) -> datetime.timedelta | str | None:
        if value := falsy_as(input_date, None):
            return to_timedelta(value)

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
class Range:
    min: float
    max: float

    def __post_init__(self) -> None:
        if not self.max:
            self.max = float("inf")

    def __contains__(self, value: float, /) -> bool:
        return self.min <= value <= self.max

    @classmethod
    def parse(cls, min: float, max: float) -> Self | None:  # noqa: A002
        if not min and not max:
            return None
        return cls(min, max)


@dataclasses.dataclass(slots=True, frozen=True)
class FileSizeRanges:
    video: Range
    image: Range
    non_media: Range


class SizeLimits(ConfigGroup):
    max_image_size: ByteSizeSerilized = ByteSize(0)
    max_non_media_size: ByteSizeSerilized = ByteSize(0)
    max_video_size: ByteSizeSerilized = ByteSize(0)
    min_image_size: ByteSizeSerilized = ByteSize(0)
    min_non_media_size: ByteSizeSerilized = ByteSize(0)
    min_video_size: ByteSizeSerilized = ByteSize(0)

    @functools.cached_property
    def ranges(self) -> FileSizeRanges:
        return FileSizeRanges(
            video=Range(
                self.min_video_size,
                self.max_video_size,
            ),
            image=Range(
                self.min_image_size,
                self.max_image_size,
            ),
            non_media=Range(
                self.min_non_media_size,
                self.max_non_media_size,
            ),
        )


@dataclasses.dataclass(slots=True, frozen=True)
class MediaDurationRanges:
    video: Range | None
    audio: Range | None


class MediaDurationLimits(ConfigGroup):
    max_video_duration: datetime.timedelta = datetime.timedelta(seconds=0)
    max_audio_duration: datetime.timedelta = datetime.timedelta(seconds=0)
    min_video_duration: datetime.timedelta = datetime.timedelta(seconds=0)
    min_audio_duration: datetime.timedelta = datetime.timedelta(seconds=0)

    @field_validator("*", mode="before")
    @staticmethod
    def parse_runtime_duration(input_date: datetime.timedelta | str | int | None) -> datetime.timedelta | str:
        """Parses `datetime.timedelta`, `str` or `int` into a timedelta format.
        for `str`, the expected format is `value unit`, ex: `5 days`, `10 minutes`, `1 year`
        valid units:
            year(s), week(s), day(s), hour(s), minute(s), second(s), millisecond(s), microsecond(s)
        for `int`, value is assumed as `days`
        """
        if input_date is None:
            return datetime.timedelta(seconds=0)
        return to_timedelta(input_date)

    @property
    def needs_ffmpeg(self) -> bool:
        return bool(
            self.min_video_duration or self.max_video_duration or self.min_audio_duration or self.max_audio_duration
        )

    @functools.cached_property
    def ranges(self) -> MediaDurationRanges:
        return MediaDurationRanges(
            video=Range.parse(
                self.min_video_duration.total_seconds(),
                self.max_video_duration.total_seconds(),
            ),
            audio=Range.parse(
                self.min_audio_duration.total_seconds(),
                self.max_audio_duration.total_seconds(),
            ),
        )


@Parameter(name="*")
class FileFilter(AliasModel):
    audio: bool = True
    images: bool = True
    videos: bool = True
    non_media: bool = True


class Filters(ConfigGroup):
    files: FileFilter = Field(default_factory=FileFilter)
    sizes: SizeLimits = Field(default_factory=SizeLimits)
    before: datetime.date | None = None
    after: datetime.date | None = None
    filename_regex: NonEmptyStrOrNone = None
    only_hosts: ListNonEmptyStr = []
    skip_hosts: ListNonEmptyStr = []
    allow_files_with_no_extension: bool = False

    @field_validator("filename_regex")
    @classmethod
    def _is_valid_regex(cls, value: str | None) -> str | None:
        if not value:
            return None
        try:
            _ = re.compile(value)
        except re.error as e:
            raise ValueError("input is not a valid regex") from e
        return value


class Jdownloader(ConfigGroup, name=None):
    enabled: Annotated[bool, Parameter(name="--jdownloader")] = False
    autostart: bool = False
    download_dir: PathOrNone = None
    whitelist: ListNonEmptyStr = []


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
        NonEmptyStrOrNone,
        AfterValidator(_format_validator(_COMMON_FIELDS | {"bitrate", "duration", "length", "sample_rate"})),
    ] = "{sort_dir}/{base_dir}/Audio/{filename}{ext}"
    "Format to generate sorted audio file"

    image: Annotated[
        NonEmptyStrOrNone, AfterValidator(_format_validator(_COMMON_FIELDS | {"height", "resolution", "width"}))
    ] = "{sort_dir}/{base_dir}/Images/{filename}{ext}"
    "Format to generate sorted image file"

    non_media: Annotated[NonEmptyStrOrNone, AfterValidator(_format_validator(_COMMON_FIELDS))] = (
        "{sort_dir}/{base_dir}/Other/{filename}{ext}"
    )
    "Format to generate sorted files of unknown type"

    video: Annotated[
        NonEmptyStrOrNone,
        AfterValidator(
            _format_validator(
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
            )
        ),
    ] = "{sort_dir}/{base_dir}/Videos/{filename}{ext}"
    "Format to generate sorted video file"
    incrementer: Annotated[NonEmptyStr, AfterValidator(_format_validator({"i"}))] = " ({i})"
    "Format for separator on name collisions"


class Sort(ConfigGroup, name=None):
    enabled: Annotated[bool, Parameter(name="--sort")] = False
    input_folder: PathOrNone = None
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
    algorithms: Annotated[tuple[Literal["xxh128", "md5", "sha256"], ...], Parameter(alias="--hashes")] = (
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
    flaresolverr: HttpURL | None = None
    proxy: HttpURL | None = None
    rate_limit: PositiveFloat = 25
    connection_timeout: PositiveFloat = 15
    read_timeout: Annotated[PositiveFloat | None, BeforeValidator(falsy_as_none)] = 300
    ssl_context: Literal["truststore", "certifi", "truststore+certifi"] | None = "truststore+certifi"
    user_agent: NonEmptyStr = "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0"

    @field_validator("ssl_context", mode="before")
    @classmethod
    def _ssl(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            value = value.lower().strip()
        return falsy_as(value, None)

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


class GenericCrawlers(ConfigGroup):
    wordpress_media: ListPydanticURL = []
    wordpress_html: ListPydanticURL = []
    discourse: ListPydanticURL = []
    chevereto: ListPydanticURL = []
