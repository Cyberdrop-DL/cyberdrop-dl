import datetime
import logging
import random
from enum import auto
from pathlib import Path
from typing import Annotated, ClassVar, Literal, override

from cyclopts import Parameter
from pydantic import BaseModel, Field, NonNegativeInt, PrivateAttr
from pydantic.types import ByteSize, NonNegativeFloat, PositiveFloat, PositiveInt

from cyberdrop_dl.constants import LOGS_DATE_FORMAT, LOGS_DATETIME_FORMAT, CIStrEnum, HashMode
from cyberdrop_dl.models import ConfigGroup, ConfigModel
from cyberdrop_dl.models.types import (
    ByteSizeSerilized,
    CSVPath,
    FalsyAsNone,
    FormatStr,
    HttpURL,
    LogLevel,
    LogPath,
    NonEmptyStr,
    Timedelta,
)
from cyberdrop_dl.models.validators import strings


class _SubFoldersInclude(ConfigModel):
    album_id: bool = False
    thread_id: bool = False
    domain: bool = True


class SubFolders(ConfigGroup, name=None):
    create: Annotated[bool, Parameter(name="--subfolders")] = True
    "Enable/disable the createtion of nested sub-folders"

    include: _SubFoldersInclude = Field(default_factory=_SubFoldersInclude)
    separate_posts_format: Annotated[
        FormatStr, strings.format_validator({"default", "title", "id", "number", "date"})
    ] = "{default}"

    separate_posts: bool = False
    "Create new subfolders for every post on a site"


class LogFiles(ConfigModel):
    main: Annotated[LogPath, Parameter(alias="--log-file")] = Path("downloader.log")
    "Path of main log file"

    download_errors: CSVPath = Path("download_errors.csv")
    "Save download errors to this file (MUST BE .csv)"

    scrape_errors: CSVPath = Path("scrape_errors.csv")
    "Save scrape errors to this file (MUST BE .csv)"

    unsupported: CSVPath = Path("unsupported.csv")
    "Save unsupported URLs to this file (MUST BE .csv)"

    last_forum_post: CSVPath = Path("last_forum_post.csv")
    "Save the URL of the last scraped post from each thread to this file (MUST BE .csv)"

    @property
    def jsonl_file(self) -> Path:
        return self.main.with_suffix(".results.jsonl")


class Logs(ConfigGroup, name=None):  # noqa: PLW1641
    level: LogLevel = "DEBUG"
    "Only log messages of this level or higher to the main log file"

    console_level: FalsyAsNone[LogLevel] = None
    "Only log messages of this level or higher to the console. An empty or `None` value will use the same level as `log_level`"

    files: LogFiles = Field(default_factory=LogFiles)
    folder: FalsyAsNone[Path] = None
    "Base folder to prepend to log files paths (if they are not absolute)"

    expire_after: FalsyAsNone[Timedelta] = None
    "Delete all log files inside `--logs.folder` if they are older that this"

    rotate: bool = False
    "Append current datetimme to every log file on each run"

    _created_at: datetime.datetime = PrivateAttr(default_factory=datetime.datetime.now)

    @property
    def effective_level(self) -> int:
        return logging.getLevelNamesMapping()[self.level]

    @property
    def effective_console_level(self) -> int:
        if not self.console_level:
            return self.effective_level

        return logging.getLevelNamesMapping()[self.console_level]

    def resolve_filenames(self, appdata_folder: Path) -> None:
        self.folder = folder = self.folder.expanduser().resolve().absolute() if self.folder else appdata_folder
        now_file_iso: str = self._created_at.strftime(LOGS_DATETIME_FORMAT)
        now_folder_iso: str = self._created_at.strftime(LOGS_DATE_FORMAT)

        def resolve(path: Path) -> Path:
            log_file = folder / path
            if self.rotate:
                file_name = f"{log_file.stem}_{now_file_iso}{log_file.suffix}"
                log_file = log_file.parent / now_folder_iso / file_name
            return log_file

        self.files = LogFiles.model_construct(
            None, **{name: resolve(value) for name, value in self.files.model_dump().items()}
        )

    @property
    def effective_log_folder(self) -> Path:
        assert self.folder
        return self.folder

    def delete_old_logs_and_folders(self) -> None:
        if not self.expire_after:
            return

        for file in (self.effective_log_folder).rglob("*"):
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


class Jdownloader(ConfigGroup, name=None):
    enabled: Annotated[bool, Parameter(name="--jdownloader")] = False
    "Send unsupported URLs to Jdownloader"

    autostart: bool = False
    "Immediately start downloads as soon as they are sent"

    download_folder: FalsyAsNone[Path] = None
    "Output path for Jdownloader. Defaults to `--download-folder`"

    whitelist: set[NonEmptyStr] = Field(default_factory=set)
    "Only send unsupported URLs from these domains to Jdownloader. An empty list means 'send all URLs'"


class SortFormats(ConfigModel):
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
        FalsyAsNone[FormatStr],
        strings.format_validator(_COMMON_FIELDS | {"bitrate", "duration", "length", "sample_rate"}),
    ] = "{sort_dir}/{base_dir}/Audio/{filename}{ext}"
    "Format to generate sorted audio file"

    image: Annotated[
        FalsyAsNone[FormatStr], strings.format_validator(_COMMON_FIELDS | {"height", "resolution", "width"})
    ] = "{sort_dir}/{base_dir}/Images/{filename}{ext}"
    "Format to generate sorted image file"

    non_media: Annotated[FalsyAsNone[FormatStr], strings.format_validator(_COMMON_FIELDS)] = (
        "{sort_dir}/{base_dir}/Other/{filename}{ext}"
    )
    "Format to generate sorted files of unknown type"

    video: Annotated[
        FalsyAsNone[FormatStr],
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

    incrementer: Annotated[FormatStr, strings.format_validator({"i"})] = " ({i})"
    "Format for separator on name collisions"


class Sort(ConfigGroup, name=None):
    enabled: Annotated[bool, Parameter(name="--sort")] = False
    "Enable/Disable file sorting at the end of a run"

    input_folder: FalsyAsNone[Path] = None
    "Base folder to scan for files. Default to the same value as `--download-folder`"

    output_folder: Path = Path("downloads/cyberdrop-dl sorted")
    "Output path to place sorted files in"

    formats: SortFormats = Field(default_factory=SortFormats)

    @property
    def needs_ffmpeg(self) -> bool:
        return bool(self.enabled and (self.formats.audio or self.formats.video))


class Dedupe(ConfigModel):
    enabled: Annotated[bool, Parameter(name="--hashing.dedupe", alias="--auto-dedupe")] = True
    "Auto delete duplicate downloads by hash"

    use_trash_bin: bool = True
    "Send deleted files to the trash bin"


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
    "List of hashes to compute for each download"

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
    "Max number of files to download simultaneously"

    concurrency_per_domain: Annotated[PositiveInt, Parameter(name="--downloads.per-domain")] = 5
    "Max number of files to download simultaneously per domain"

    attempts: PositiveInt = 2

    delay: NonNegativeFloat = 0.0
    "Number of seconds to wait before starting downloads"

    slow_speed: ByteSizeSerilized = ByteSize(0)
    "Skip downloads if their speed is below this value for more than 10 seconds. Set to 0 to disable"

    speed_limit: ByteSizeSerilized = ByteSize(0)
    "Max speed rate (in bytes per second) to limit downloads (combined)"

    jitter: NonNegativeFloat = 0
    "Wait a random additional number of seconds in between 0 and <jitter> before downloads"

    skip_and_mark_completed: bool = False
    "Skip all downloads and mark them as downloaded on the database"

    concurrent_segments: PositiveInt = 10
    """Allow up to `<N>` HLS segments to be downloaded concurrently"""

    @property
    def total_delay(self) -> NonNegativeFloat:
        return self.delay + random.uniform(0, self.jitter)


class Network(ConfigGroup):
    dump_responses: bool = False
    "Save text/HTML/JSON responses to disk (flaresolverr responses are excluded)"

    flaresolverr: FalsyAsNone[HttpURL] = None
    "HTTP URL of an existing flaresolverr instance"

    proxy: FalsyAsNone[HttpURL] = None
    "HTTP/HTTPS proxy"

    rate_limit: PositiveFloat = 25
    "Max number of requests per second (only used while scraping)"

    connection_timeout: PositiveFloat = 15
    read_timeout: FalsyAsNone[PositiveFloat] = 300
    ssl_context: FalsyAsNone[
        Annotated[
            Literal["truststore", "certifi", "truststore+certifi"],
            strings.pre_validator(to_lower=True, strip=True),
        ]
    ] = "truststore+certifi"
    user_agent: NonEmptyStr = "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0"
    impersonate: FalsyAsNone[Literal["chrome", "edge", "safari", "safari_ios", "chrome_android", "firefox"]] = None
    "Use this target as impersonation for all scrape requests"

    @property
    def curl_timeout(self) -> float | tuple[float, float]:
        if self.read_timeout is None:
            return self.connection_timeout
        return self.connection_timeout, self.read_timeout


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


class MaxChildren(ConfigGroup, name=None):
    forum: NonNegativeInt = 0
    "Do not scrape more that this number of URLs inside a forum thread"
    forum_post: NonNegativeInt = 0
    "Do not scrape more that this number of URLs inside an individual a forum post"
    profile: NonNegativeInt = 0
    "Do not scrape more that this number of URLs in a profile"
    album: NonNegativeInt = 0
    "Do not scrape more that this number of URLs in a album"
