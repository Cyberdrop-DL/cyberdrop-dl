from __future__ import annotations

import dataclasses
import logging
import os
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from pydantic.types import ByteSize

from cyberdrop_dl import __version__, env, ffmpeg, yaml
from cyberdrop_dl.cli import CLIargs
from cyberdrop_dl.config import Config
from cyberdrop_dl.database import Database
from cyberdrop_dl.dedupe import Czkawka
from cyberdrop_dl.hasher import Hasher
from cyberdrop_dl.logs import capture_logs, log_spacer
from cyberdrop_dl.managers.client_manager import ClientManager
from cyberdrop_dl.managers.logs import LogManager
from cyberdrop_dl.sorter import Sorter
from cyberdrop_dl.utils import get_system_information

if TYPE_CHECKING:
    from collections.abc import Sequence
    from os import PathLike

    from cyberdrop_dl.progress.dedupe import DedupeStats
    from cyberdrop_dl.progress.hashing import HashingStats
    from cyberdrop_dl.progress.scraping.errors import UIError
    from cyberdrop_dl.progress.sorting import SortStats
    from cyberdrop_dl.scrape_mapper import ScrapeMapper, ScrapeStats
    from cyberdrop_dl.url_objects import MediaItem


logger = logging.getLogger(__name__)


class Manager:
    def __init__(
        self,
        cli_args: CLIargs | None = None,
        appdata: AppData | None = None,
        config: Config | None = None,
    ) -> None:
        self.cache: dict[str, Any] = {}
        self._appdata: AppData | None = appdata
        self.cli_args: CLIargs = cli_args or CLIargs()
        self._config: Config | None = config

        self._completed_downloads: list[MediaItem] = []
        self.hasher: Hasher = Hasher(self)
        self.logs: LogManager = LogManager.from_manager(self)
        self.scrape_mapper: ScrapeMapper
        self.database: Database
        self.client_manager: ClientManager
        self.deduper: Czkawka
        self.sorter: Sorter

    @property
    def appdata(self) -> AppData:
        if self._appdata is None:
            self._appdata = AppData.default()
        return self._appdata

    @property
    def config(self) -> Config:
        if self._config is None:
            self._config = Config.from_manager(self)
        return self._config

    def resolve_paths(self) -> None:
        self.appdata.mkdirs()
        self.config.settings.resolve_paths()
        self.logs = LogManager.from_manager(self)
        self.logs.delete_old_logs()

    async def __aenter__(self) -> Self:
        cache_file = self.appdata.cache_file
        try:
            self.cache.update(yaml.load(cache_file))
        except FileNotFoundError:
            cache_file.parent.mkdir(exist_ok=True, parents=True)
            cache_file.touch()
        return self

    async def __aexit__(self, *_) -> None:
        self.cache["version"] = __version__
        yaml.save(self.appdata.cache_file, self.cache)

    def add_completed(self, media_item: MediaItem) -> None:
        if media_item.is_segment:
            return
        self._completed_downloads.append(media_item)

    @property
    def completed_downloads(self) -> list[MediaItem]:
        return self._completed_downloads

    async def async_startup(self) -> None:
        self._log_config_settings()
        self.async_db_hash_startup()

        self.client_manager = ClientManager(self)

    def async_db_hash_startup(self) -> None:
        self.database = Database(
            self.appdata.db_file,
            self.config.settings.runtime_options.ignore_history,
        )
        self.deduper = Czkawka(
            self.hasher.download_folder,
            self.database,
            self.config.settings.dupe_cleanup_options.send_deleted_to_trash,
        )
        self.sorter = Sorter.from_manager(self)

    def _log_config_settings(self) -> None:
        auth = {site: all(credentials.values()) for site, credentials in self.config.auth.model_dump().items()}
        config_settings = self.config.settings.model_copy()
        config_settings.runtime_options.deep_scrape = self.config.deep_scrape

        logger.info(f"Running cyberdrop-dl v{__version__}")

        logger.debug(
            {
                "System": get_system_information(),
                "Config file": self.config.source,
                "URLs file": self.config.settings.files.input_file,
                "Apprise URLs": tuple(url.format(dump_secret=False) for url in self.config.apprise_urls),
                "Download folder": self.config.settings.files.download_folder,
                "Database file": self.appdata.db_file,
                "CLI options": self.cli_args.model_dump(mode="json"),
                "Auth": auth,
                "Settings": config_settings.model_dump(mode="json"),
                "Global settings": self.config.global_settings.model_dump(mode="json"),
                "Enviroment": env.ALL_VARS,
                "Enviroment resolved": env.ALL_VARS_RESOLVED,
                "argv": tuple(sys.argv[1:]),
            }
        )

        if ffmpeg.is_installed():
            logger.debug(
                {
                    "ffmpeg": {
                        "binary": ffmpeg.which_ffmpeg(),
                        "version": ffmpeg.version(),
                    },
                    "ffprobe": {
                        "binary": ffmpeg.which_ffprobe(),
                        "version": ffmpeg.ffprobe_version(),
                    },
                }
            )

        try:
            db_size = self.appdata.db_file.stat().st_size
        except FileNotFoundError:
            db_size = 0

        logger.debug("Database size: %s", ByteSize(db_size).human_readable(decimal=True))

        if not ffmpeg.is_installed():
            msg = "ffmpeg is not installed. HLS downloads will fail"
            if os.name == "nt":
                msg += ". Get it from: https://www.gyan.dev/ffmpeg/builds/"

            logger.warning(msg)

    def print_stats(self, stats: ScrapeStats) -> str:
        if not self.cli_args.print_stats:
            return ""

        log_spacer()

        with capture_logs() as stream:
            self._print_stats(stats)

        return stream.getvalue()

    def _print_stats(self, stats: ScrapeStats) -> None:

        elapsed = timedelta(seconds=int(time.monotonic() - stats.start_time))
        total_data_written = ByteSize(self.scrape_mapper.tui.downloads.bytes_downloaded).human_readable(decimal=True)

        logger.info("Run Stats:", extra={"color": "cyan"})
        logger.info(f"  Config file: {self.config.source}")
        logger.info(f"  URLs source: {stats.source}")
        logger.info(f"  URLs: {stats.count:,}")
        logger.info(f"  URL groups: {len(stats.unique_groups):,}")
        logger.info(f"  Logs folder: {self.config.settings.logs.log_folder}")
        logger.info(f"  Total runtime: {elapsed}")
        logger.info(f"  Total downloaded data: {total_data_written}")

        if stats.domain_stats:
            log_spacer()
            logger.info("URLs by domain (includes children):", extra={"color": "cyan"})

            def lines():
                for domain, count in sorted(stats.domain_stats.items()):
                    yield f" - {domain}: {count:,}"

            logger.info("\n".join(lines()))

        log_spacer()
        logger.info("Download Stats:", extra={"color": "cyan"})
        logger.info(f"  Downloaded: {self.scrape_mapper.tui.files.stats.completed:,} files")
        logger.info(f"  Skipped (by config): {self.scrape_mapper.tui.files.stats.skipped:,} files")
        logger.info(
            f"  Skipped (previously downloaded): {self.scrape_mapper.tui.files.stats.previously_completed:,} files"
        )
        logger.info(f"  Failed: {self.scrape_mapper.tui.files.stats.failed:,} files")

        log_spacer()
        logger.info("Unsupported URLs Stats:", extra={"color": "cyan"})
        logger.info(f"  Sent to Jdownloader: {self.scrape_mapper.tui.scrape_errors.sent_to_jdownloader:,}")
        logger.info(f"  Skipped: {self.scrape_mapper.tui.scrape_errors.skipped:,}")

        self.print_hashing_stats(self.hasher.stats)
        self.print_dedupe_stats(self.deduper.stats)
        # self.print_sort_stats()
        self.print_errors()

    def print_sort_stats(self, stats: SortStats):
        log_spacer()
        logger.info("Sort Stats:", extra={"color": "cyan"})
        logger.info(f"  Audios: {stats.audios:,}")
        logger.info(f"  Images: {stats.images:,}")
        logger.info(f"  Videos: {stats.videos:,}")
        logger.info(f"  Other files: {stats.others:,}")

    def print_errors(self) -> None:
        _log_errors(
            tuple(self.scrape_mapper.tui.scrape_errors),
            tuple(self.scrape_mapper.tui.download_errors),
        )

    def print_hashing_stats(self, stats: HashingStats) -> None:
        log_spacer()
        logger.info("Checksum Stats:", extra={"color": "cyan"})
        logger.info(f"  Newly hashed: {stats.new_hashed:,} files")
        logger.info(f"  Previously hashed: {stats.prev_hashed:,} files")

    def print_dedupe_stats(self, stats: DedupeStats) -> None:
        log_spacer()
        logger.info("Dedupe Stats:", extra={"color": "cyan"})
        logger.info(f"  Deleted (duplicates of previous downloads): {stats.deleted:,} files")
        logger.info(f"  Errors: {stats.total - stats.deleted:,} files")


def _log_errors(scrape_errors: Sequence[UIError], download_errors: Sequence[UIError]) -> None:
    error_codes = (error.code for error in (*scrape_errors, *download_errors) if error.code is not None)

    try:
        padding = len(str(max(error_codes)))
    except ValueError:
        padding = 0

    for title, errors in (
        ("Scrape Errors:", scrape_errors),
        ("Download Errors:", download_errors),
    ):
        log_spacer()
        logger.info(title, extra={"color": "cyan"})
        if not errors:
            logger.info(f"  {'None':>{padding}}", extra={"color": "green"})
            continue

        for error in errors:
            logger.info(f"  {error.format(padding)}", extra={"color": "red"})


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class AppData:
    path: Path
    cache_file: Path
    config_file: Path
    db_file: Path

    cache: Path
    cookies: Path
    configs: Path

    @classmethod
    def default(cls) -> Self:
        return cls.from_path(Path.cwd())

    @staticmethod
    def _resolve_win_path(path: Path) -> Path:
        # Detect the real path when running in sandboxed interpreter (ex: UWP Python)
        # https://github.com/Cyberdrop-DL/cyberdrop-dl/issues/1700#issuecomment-4317561031
        # https://learn.microsoft.com/en-us/windows/msix/desktop/flexible-virtualization#default-msix-behavior
        anchor = path / "cyberdrop_dl.anchor"
        path.mkdir(parents=True, exist_ok=True)
        anchor.touch()
        real_path = anchor.resolve().parent
        if path != real_path:
            logger.warning("Windows virtualized path detected at '%s'. Real destination: '%s'", path, real_path)
        anchor.unlink()
        try:
            real_path.rmdir()
        except OSError:
            pass
        return real_path

    @classmethod
    def from_path(cls, path: Path) -> Self:
        path = path.expanduser().resolve().absolute() / "AppData"
        if os.name == "nt":
            path = cls._resolve_win_path(path)

        cache = path / "Cache"
        configs = path / "Configs"
        return cls(
            path=path,
            cache=cache,
            configs=configs,
            cookies=path / "Cookies",
            config_file=configs / "Default" / "settings.yaml",
            cache_file=cache / "cache.yaml",
            db_file=cache / "cyberdrop.db",
        )

    def __truediv__(self, other: PathLike[str]):
        try:
            return self.path / other
        except TypeError:
            return NotImplemented

    def __fspath__(self) -> str:
        return str(self)

    def __str__(self) -> str:
        return str(self.path)

    def mkdirs(self) -> None:
        for dir in (self.cache, self.configs, self.cookies):
            dir.mkdir(parents=True, exist_ok=True)
