# ruff: noqa: RUF012
import dataclasses
import logging
import random
import re
from datetime import date, datetime, timedelta
from functools import cached_property
from pathlib import Path
from typing import Annotated, Any, Literal, Self, override

import aiohttp
from cyclopts import Parameter
from pydantic import (
    BaseModel,
    ByteSize,
    NonNegativeFloat,
    NonNegativeInt,
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
    Hashing,
)
from cyberdrop_dl.models import AppriseURL, SettingsGroup
from cyberdrop_dl.models.types import (
    ByteSizeSerilized,
    ListNonEmptyStr,
    ListNonNegativeInt,
    ListPydanticURL,
    LogPath,
    MainLogPath,
    NonEmptyStr,
    NonEmptyStrOrNone,
    PathOrNone,
)
from cyberdrop_dl.models.validators import falsy_as, falsy_as_none, to_timedelta
from cyberdrop_dl.utils import delete_empty_files_and_folders
from cyberdrop_dl.utils.strings import validate_format_string

_SORTING_COMMON_FIELDS = {
    "base_dir",
    "ext",
    "file_date",
    "file_date_iso",
    "file_date_us",
    "filename",
    "parent_dir",
    "sort_dir",
}


class DownloadOptions(SettingsGroup):
    block_download_sub_folders: bool = False
    mtime: bool = True
    include_album_id_in_folder_name: bool = False
    include_thread_id_in_folder_name: bool = False
    max_number_of_children: ListNonNegativeInt = []
    remove_domains_from_folder_names: bool = False
    separate_posts_format: NonEmptyStr = "{default}"
    separate_posts: bool = False
    skip_download_mark_completed: bool = False
    max_thread_depth: NonNegativeInt = 0
    max_thread_folder_depth: NonNegativeInt | None = None

    @field_validator("separate_posts_format", mode="after")
    @classmethod
    def valid_format(cls, value: str) -> str:
        valid_keys = {"default", "title", "id", "number", "date"}
        validate_format_string(value, valid_keys)
        return value


class Logs(SettingsGroup):  # noqa: PLW1641
    download_error_urls: LogPath = Path("Download_Error_URLs.csv")
    log_folder: Path = DEFAULT_APP_STORAGE / "Logs"
    logs_expire_after: timedelta | None = None
    main_log: MainLogPath = Path("downloader.log")
    rotate_logs: bool = False
    scrape_error_urls: LogPath = Path("Scrape_Error_URLs.csv")
    unsupported_urls: LogPath = Path("Unsupported_URLs.csv")
    webhook: Annotated[AppriseURL | None, Parameter(show=False)] = None

    _created_at: datetime = PrivateAttr(default_factory=datetime.now)

    @field_validator("webhook", mode="before")
    @classmethod
    def handle_falsy(cls, value: str) -> str | None:
        return falsy_as(value, None)

    @field_validator("logs_expire_after", mode="before")
    @staticmethod
    def parse_logs_duration(input_date: timedelta | str | int | None) -> timedelta | str | None:
        if value := falsy_as(input_date, None):
            return to_timedelta(value)

    def resolve_filenames(self) -> None:
        object.__setattr__(self, "log_folder", self.log_folder.expanduser().resolve().absolute())
        now_file_iso: str = self._created_at.strftime(LOGS_DATETIME_FORMAT)
        now_folder_iso: str = self._created_at.strftime(LOGS_DATE_FORMAT)
        for name, log_file in vars(self).items():
            if name == "log_folder" or not isinstance(log_file, Path) or log_file.suffix not in {".csv", ".log"}:
                continue

            log_file = self.log_folder / log_file

            if self.rotate_logs:
                file_name = f"{log_file.stem}_{now_file_iso}{log_file.suffix}"
                log_file = log_file.parent / now_folder_iso / file_name

            object.__setattr__(self, name, log_file)

    def delete_old_logs_and_folders(self) -> None:
        if not self.logs_expire_after:
            return

        for file in self.log_folder.rglob("*"):
            if file.suffix.lower() not in {".log", ".csv"}:
                continue

            if (self._created_at - datetime.fromtimestamp(file.stat().st_ctime)) > self.logs_expire_after:  # noqa: DTZ006
                file.unlink()

        delete_empty_files_and_folders(self.log_folder)

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
    other: Range


class FileSizeLimits(SettingsGroup):
    max_image_size: ByteSizeSerilized = ByteSize(0)
    max_other_size: ByteSizeSerilized = ByteSize(0)
    max_video_size: ByteSizeSerilized = ByteSize(0)
    min_image_size: ByteSizeSerilized = ByteSize(0)
    min_other_size: ByteSizeSerilized = ByteSize(0)
    min_video_size: ByteSizeSerilized = ByteSize(0)

    @cached_property
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
            other=Range(
                self.min_other_size,
                self.max_other_size,
            ),
        )


@dataclasses.dataclass(slots=True, frozen=True)
class MediaDurationRanges:
    video: Range | None
    audio: Range | None


class MediaDurationLimits(SettingsGroup):
    max_video_duration: timedelta = timedelta(seconds=0)
    max_audio_duration: timedelta = timedelta(seconds=0)
    min_video_duration: timedelta = timedelta(seconds=0)
    min_audio_duration: timedelta = timedelta(seconds=0)

    @field_validator("*", mode="before")
    @staticmethod
    def parse_runtime_duration(input_date: timedelta | str | int | None) -> timedelta | str:
        """Parses `datetime.timedelta`, `str` or `int` into a timedelta format.
        for `str`, the expected format is `value unit`, ex: `5 days`, `10 minutes`, `1 year`
        valid units:
            year(s), week(s), day(s), hour(s), minute(s), second(s), millisecond(s), microsecond(s)
        for `int`, value is assumed as `days`
        """
        if input_date is None:
            return timedelta(seconds=0)
        return to_timedelta(input_date)

    @property
    def needs_ffmpeg(self) -> bool:
        return bool(
            self.min_video_duration or self.max_video_duration or self.min_audio_duration or self.max_audio_duration
        )

    @cached_property
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


class IgnoreOptions(SettingsGroup):
    exclude_audio: bool = False
    exclude_images: bool = False
    exclude_other: bool = False
    exclude_videos: bool = False
    filename_regex_filter: NonEmptyStrOrNone = None
    ignore_coomer_ads: bool = False
    ignore_coomer_post_content: bool = True
    only_hosts: ListNonEmptyStr = []
    skip_hosts: ListNonEmptyStr = []
    exclude_files_with_no_extension: bool = True
    exclude_before: date | None = None
    exclude_after: date | None = None

    @field_validator("filename_regex_filter")
    @classmethod
    def is_valid_regex(cls, value: str | None) -> str | None:
        if not value:
            return None
        try:
            _ = re.compile(value)
        except re.error as e:
            raise ValueError("input is not a valid regex") from e
        return value


class RuntimeOptions(SettingsGroup):
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"
    "Only log messages of this level or higher to the main log file"
    console_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None = None
    "Only log messages of this level or higher to the console. An empty or `None` value will use the same level as `log_level`"
    deep_scrape: bool = False
    delete_partial_files: bool = False
    ignore_history: bool = False
    jdownloader_autostart: bool = False
    jdownloader_download_dir: PathOrNone = None
    jdownloader_whitelist: ListNonEmptyStr = []

    send_unsupported_to_jdownloader: bool = False
    skip_check_for_empty_folders: bool = False
    skip_check_for_partial_files: bool = False
    slow_download_speed: ByteSizeSerilized = ByteSize(0)

    @field_validator("log_level", "console_log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> Any:
        value = falsy_as_none(value)
        if type(value) is str:
            return value.upper()
        return value

    @property
    def effective_log_level(self) -> int:
        return logging.getLevelNamesMapping()[self.log_level]

    @property
    def effective_console_log_level(self) -> int:
        if not self.console_log_level:
            return self.effective_log_level

        return logging.getLevelNamesMapping()[self.console_log_level]


class Sorting(SettingsGroup):
    scan_folder: PathOrNone = None
    sort_downloads: bool = False
    sort_folder: Path = DEFAULT_DOWNLOAD_STORAGE / "Cyberdrop-DL Sorted Downloads"
    sort_incrementer_format: NonEmptyStr = " ({i})"
    sorted_audio: NonEmptyStrOrNone = "{sort_dir}/{base_dir}/Audio/{filename}{ext}"
    sorted_image: NonEmptyStrOrNone = "{sort_dir}/{base_dir}/Images/{filename}{ext}"
    sorted_other: NonEmptyStrOrNone = "{sort_dir}/{base_dir}/Other/{filename}{ext}"
    sorted_video: NonEmptyStrOrNone = "{sort_dir}/{base_dir}/Videos/{filename}{ext}"

    @property
    def needs_ffmpeg(self) -> bool:
        return bool(self.sort_downloads and (self.sorted_audio or self.sorted_image or self.sorted_video))

    @field_validator("sort_incrementer_format", mode="after")
    @classmethod
    def valid_sort_incrementer_format(cls, value: str | None) -> str | None:
        if value is not None:
            valid_keys = {"i"}
            validate_format_string(value, valid_keys)
        return value

    @field_validator("sorted_audio", mode="after")
    @classmethod
    def valid_sorted_audio(cls, value: str | None) -> str | None:
        if value is not None:
            valid_keys = _SORTING_COMMON_FIELDS | {"bitrate", "duration", "length", "sample_rate"}
            validate_format_string(value, valid_keys)
        return value

    @field_validator("sorted_image", mode="after")
    @classmethod
    def valid_sorted_image(cls, value: str | None) -> str | None:
        if value is not None:
            valid_keys = _SORTING_COMMON_FIELDS | {"height", "resolution", "width"}
            validate_format_string(value, valid_keys)
        return value

    @field_validator("sorted_other", mode="after")
    @classmethod
    def valid_sorted_other(cls, value: str | None) -> str | None:
        if value is not None:
            valid_keys = _SORTING_COMMON_FIELDS | {"bitrate", "duration", "length", "sample_rate"}
            validate_format_string(value, valid_keys)
        return value

    @field_validator("sorted_video", mode="after")
    @classmethod
    def valid_sorted_video(cls, value: str | None) -> str | None:
        if value is not None:
            valid_keys = _SORTING_COMMON_FIELDS | {
                "codec",
                "duration",
                "fps",
                "height",
                "length",
                "resolution",
                "width",
            }
            validate_format_string(value, valid_keys)
        return value


class Cookies(SettingsGroup):
    cookies: Path | None = None
    "File/folder to import cookies from (.txt Netscape files)"


class DupeCleanup(SettingsGroup):
    hashes: tuple[Literal["xxh128", "md5", "sha256"], ...] = "xxh128", "md5", "sha256"
    auto_dedupe: bool = True
    hashing: Hashing = Hashing.IN_PLACE
    send_deleted_to_trash: bool = True
    _extra_hashes: tuple[Literal["md5", "sha256"], ...] = ()

    @override
    def model_post_init(self, *_) -> None:
        self.re_compute()

    def re_compute(self) -> None:
        hashes = set(self.hashes)
        if (xxhash := "xxh128") not in hashes:
            self.hashes = xxhash, *hashes
        hashes.discard(xxhash)
        self._extra_hashes = tuple(sorted(hashes))  # pyright: ignore[reportAttributeAccessIssue]

    @property
    def extra_hashes(self) -> tuple[Literal["md5", "sha256"], ...]:
        return self._extra_hashes


class RateLimiting(SettingsGroup):
    download_attempts: PositiveInt = 2
    download_delay: NonNegativeFloat = 0.0
    download_speed_limit: ByteSizeSerilized = ByteSize(0)
    jitter: NonNegativeFloat = 0
    max_simultaneous_downloads_per_domain: PositiveInt = 5
    max_simultaneous_downloads: PositiveInt = 15
    rate_limit: PositiveFloat = 25

    connection_timeout: PositiveFloat = 15
    read_timeout: PositiveFloat | None = 300
    concurrent_segments: PositiveInt = 10
    """Allow up to `<N>` HLS segments to be downloaded concurrently"""

    @field_validator("read_timeout", mode="before")
    @classmethod
    def parse_timeouts(cls, value: object) -> object | None:
        return falsy_as_none(value)

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

    @property
    def total_delay(self) -> NonNegativeFloat:
        """download_delay + jitter"""
        return self.download_delay + random.uniform(0, self.jitter)


class UIOptions(SettingsGroup):
    refresh_rate: PositiveFloat = 10.0


class GenericCrawlers(SettingsGroup):
    wordpress_media: ListPydanticURL = []
    wordpress_html: ListPydanticURL = []
    discourse: ListPydanticURL = []
    chevereto: ListPydanticURL = []
