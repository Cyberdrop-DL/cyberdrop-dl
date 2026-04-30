# ruff: noqa: RUF012
import re
from datetime import date, datetime, timedelta
from logging import DEBUG
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter
from pydantic import BaseModel, ByteSize, Field, NonNegativeInt, PrivateAttr, field_validator

from cyberdrop_dl.constants import (
    DEFAULT_APP_STORAGE,
    DEFAULT_DOWNLOAD_STORAGE,
    LOGS_DATE_FORMAT,
    LOGS_DATETIME_FORMAT,
    Browser,
    Hashing,
)
from cyberdrop_dl.models import AliasModel, AppriseURL, SettingsGroup
from cyberdrop_dl.models.types import (
    ByteSizeSerilized,
    ListNonEmptyStr,
    ListNonNegativeInt,
    LogPath,
    MainLogPath,
    NonEmptyStr,
    NonEmptyStrOrNone,
    PathOrNone,
)
from cyberdrop_dl.models.validators import falsy_as, to_timedelta
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
    disable_download_attempt_limit: bool = False
    disable_file_timestamps: bool = False
    include_album_id_in_folder_name: bool = False
    include_thread_id_in_folder_name: bool = False
    maximum_number_of_children: ListNonNegativeInt = []
    remove_domains_from_folder_names: bool = False
    remove_generated_id_from_filenames: bool = False
    scrape_single_forum_post: bool = False
    separate_posts_format: NonEmptyStr = "{default}"
    separate_posts: bool = False
    skip_download_mark_completed: bool = False
    maximum_thread_depth: NonNegativeInt = 0
    maximum_thread_folder_depth: NonNegativeInt | None = None

    @field_validator("separate_posts_format", mode="after")
    @classmethod
    def valid_format(cls, value: str) -> str:
        valid_keys = {"default", "title", "id", "number", "date"}
        validate_format_string(value, valid_keys)
        return value


class Files(SettingsGroup):
    download_folder: Annotated[Path, Parameter(alias=("--output", "-o", "-d"))] = Field(
        default=DEFAULT_DOWNLOAD_STORAGE, validation_alias="d"
    )
    dump_json: Annotated[bool, Parameter(alias="-j")] = Field(default=False, validation_alias="j")
    input_file: Annotated[Path, Parameter(alias="-i")] = Field(default=Path("URLs.txt"), validation_alias="i")
    save_pages_html: bool = False


class Logs(SettingsGroup):
    download_error_urls: LogPath = Path("Download_Error_URLs.csv")
    last_forum_post: LogPath = Path("Last_Scraped_Forum_Posts.csv")
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
            if name == "log_folder" or not isinstance(log_file, Path) or log_file.suffix not in (".csv", ".log"):
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
            if file.suffix.lower() not in (".log", ".csv"):
                continue

            if (self._created_at - datetime.fromtimestamp(file.stat().st_ctime)) > self.logs_expire_after:
                file.unlink()

        _ = delete_empty_files_and_folders(self.log_folder)

    def __eq__(self, other: object) -> bool:
        # Exclude _created_at from compare (AKA __pydantic_private__)
        if not isinstance(other, BaseModel):
            return NotImplemented

        self_type = self.__pydantic_generic_metadata__["origin"] or self.__class__
        other_type = other.__pydantic_generic_metadata__["origin"] or other.__class__

        if not (self_type == other_type and self.__pydantic_extra__ == other.__pydantic_extra__):
            return False

        return self.__dict__ == other.__dict__


class FileSizeLimits(SettingsGroup):
    maximum_image_size: ByteSizeSerilized = ByteSize(0)
    maximum_other_size: ByteSizeSerilized = ByteSize(0)
    maximum_video_size: ByteSizeSerilized = ByteSize(0)
    minimum_image_size: ByteSizeSerilized = ByteSize(0)
    minimum_other_size: ByteSizeSerilized = ByteSize(0)
    minimum_video_size: ByteSizeSerilized = ByteSize(0)


class MediaDurationLimits(SettingsGroup):
    maximum_video_duration: timedelta = timedelta(seconds=0)
    maximum_audio_duration: timedelta = timedelta(seconds=0)
    minimum_video_duration: timedelta = timedelta(seconds=0)
    minimum_audio_duration: timedelta = timedelta(seconds=0)

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
    console_log_level: NonNegativeInt = 100
    deep_scrape: bool = False
    delete_partial_files: bool = False
    ignore_history: bool = False
    jdownloader_autostart: bool = False
    jdownloader_download_dir: PathOrNone = None
    jdownloader_whitelist: ListNonEmptyStr = []
    log_level: NonNegativeInt = DEBUG
    send_unsupported_to_jdownloader: bool = False
    skip_check_for_empty_folders: bool = False
    skip_check_for_partial_files: bool = False
    slow_download_speed: ByteSizeSerilized = ByteSize(0)
    update_last_forum_post: bool = True


class Sorting(SettingsGroup):
    scan_folder: PathOrNone = None
    sort_downloads: bool = False
    sort_folder: Path = DEFAULT_DOWNLOAD_STORAGE / "Cyberdrop-DL Sorted Downloads"
    sort_incrementer_format: NonEmptyStr = " ({i})"
    sorted_audio: NonEmptyStrOrNone = "{sort_dir}/{base_dir}/Audio/{filename}{ext}"
    sorted_image: NonEmptyStrOrNone = "{sort_dir}/{base_dir}/Images/{filename}{ext}"
    sorted_other: NonEmptyStrOrNone = "{sort_dir}/{base_dir}/Other/{filename}{ext}"
    sorted_video: NonEmptyStrOrNone = "{sort_dir}/{base_dir}/Videos/{filename}{ext}"

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


class BrowserCookies(SettingsGroup):
    auto_import: bool = False
    browser: Browser | None = Browser.firefox
    sites: list[str] = Field(default_factory=list)


class DupeCleanup(SettingsGroup):
    add_md5_hash: bool = False
    add_sha256_hash: bool = False
    auto_dedupe: bool = True
    hashing: Hashing = Hashing.IN_PLACE
    send_deleted_to_trash: bool = True


@Parameter(name="*")
class ConfigSettings(AliasModel):
    browser_cookies: BrowserCookies = BrowserCookies()
    download_options: DownloadOptions = DownloadOptions()
    dupe_cleanup_options: DupeCleanup = DupeCleanup()
    file_size_limits: FileSizeLimits = FileSizeLimits()
    media_duration_limits: MediaDurationLimits = MediaDurationLimits()
    files: Files = Files()
    ignore_options: IgnoreOptions = IgnoreOptions()
    logs: Logs = Logs()
    runtime_options: RuntimeOptions = RuntimeOptions()
    sorting: Sorting = Sorting()
    _resolved: bool = False

    def resolve_paths(self) -> None:
        if self._resolved:
            return

        self.logs.resolve_filenames()
        self._resolve_paths(self)
        self.logs.delete_old_logs_and_folders()
        self._resolved = True

    @classmethod
    def _resolve_paths(cls, model: BaseModel) -> None:

        for name, value in vars(model).items():
            if isinstance(value, Path):
                if "{config}" in str(value):
                    raise RuntimeError(f"Using '{{config}}' as reference on a path is no longer support: {value}")

                object.__setattr__(model, name, value.expanduser().resolve().absolute())

            elif isinstance(value, BaseModel):
                cls._resolve_paths(value)
