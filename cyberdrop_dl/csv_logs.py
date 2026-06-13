from __future__ import annotations

import asyncio
import csv
import dataclasses
import logging
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Self

from cyberdrop_dl import constants
from cyberdrop_dl.exceptions import get_origin
from cyberdrop_dl.utils import json
from cyberdrop_dl.utils.filepath import sanitize_filename

if TYPE_CHECKING:
    import datetime
    from collections.abc import Iterable, Iterator

    from yarl import URL

    from cyberdrop_dl.clients.response import AbstractResponse
    from cyberdrop_dl.manager import Manager
    from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem


logger = logging.getLogger(__name__)

_CSV_DELIMITER = ","


@dataclasses.dataclass(slots=True, kw_only=True)
class CSVFiles:
    main_log: Path
    unsupported_urls_log: Path
    download_error_log: Path
    scrape_error_log: Path
    jsonl_file: Path = dataclasses.field(init=False)

    def __iter__(self) -> Iterator[Path]:
        return iter(dataclasses.astuple(self))

    def __post_init__(self) -> None:
        self.jsonl_file = self.main_log.with_suffix(".results.jsonl")


@dataclasses.dataclass(slots=True)
class CSVLogsManager:
    files: CSVFiles
    task_group: asyncio.TaskGroup = dataclasses.field(init=False, default_factory=asyncio.TaskGroup)
    _file_locks: dict[Path, asyncio.Lock] = dataclasses.field(
        init=False, default_factory=lambda: defaultdict(asyncio.Lock)
    )
    _has_headers: set[Path] = dataclasses.field(init=False, default_factory=set)
    _ready: bool = dataclasses.field(init=False, default=False)
    _responses_folder: Path = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self._responses_folder = self.files.main_log.parent / "cdl_responses"

    @classmethod
    def from_manager(cls, manager: Manager) -> Self:
        files = CSVFiles(
            main_log=manager.config.logs.main_log,
            unsupported_urls_log=manager.config.logs.unsupported_urls,
            download_error_log=manager.config.logs.download_error_urls,
            scrape_error_log=manager.config.logs.scrape_error_urls,
        )
        return cls(files)

    def delete_old_logs(self) -> None:
        if self._ready:
            return
        for path in self.files:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            else:
                logger.warning(f"Deleted conflicting old log file: '{path}'")

        self._ready = True

    async def write_jsonl(self, data: Iterable[dict[str, Any]]) -> None:
        async with self._file_locks[self.files.jsonl_file]:
            await asyncio.to_thread(json.dump_jsonl, data, self.files.jsonl_file)

    async def _write_to_csv(self, file: Path, **row: object) -> None:
        async with self._file_locks[file]:
            is_first_write = file not in self._has_headers
            self._has_headers.add(file)

            def write() -> None:
                if is_first_write:
                    file.parent.mkdir(parents=True, exist_ok=True)

                with file.open("a", encoding="utf8", newline="") as csv_file:
                    writer = csv.DictWriter(
                        csv_file,
                        fieldnames=tuple(row),
                        delimiter=_CSV_DELIMITER,
                        quoting=csv.QUOTE_ALL,
                    )
                    if is_first_write:
                        writer.writeheader()
                    writer.writerow(row)

            await asyncio.to_thread(write)

    def write_unsupported(self, url: URL, origin: URL | None = None) -> None:
        """Writes to the unsupported urls log."""
        _ = self.task_group.create_task(self._write_to_csv(self.files.unsupported_urls_log, url=url, origin=origin))

    def write_download_error(self, media_item: MediaItem, error_message: str) -> None:
        """Writes to the download error log."""
        origin = get_origin(media_item)
        _ = self.task_group.create_task(
            self._write_to_csv(
                self.files.download_error_log,
                url=media_item.url,
                error=error_message,
                referer=media_item.referer,
                origin=origin,
            )
        )

    def write_scrape_error(self, url: URL | str, error_message: str, origin: URL | Path | None = None) -> None:
        """Writes to the scrape error log."""
        _ = self.task_group.create_task(
            self._write_to_csv(self.files.scrape_error_log, url=url, error=error_message, origin=origin)
        )

    def write_response(
        self,
        url: AbsoluteHttpURL,
        response: AbstractResponse[Any],
        exc: Exception | None = None,
    ) -> None:
        _ = self.task_group.create_task(
            asyncio.to_thread(
                _write_resp_to_disk,
                self._responses_folder,
                url,
                response,
                exc,
            )
        )


def _write_resp_to_disk(
    folder: Path,
    url: AbsoluteHttpURL,
    response: AbstractResponse[Any],
    exc: Exception | None = None,
) -> None:
    ext = ".json" if "json" in response.content_type else ".html"
    file = _prepare_resp_file(folder, url, response.created_at, ext)
    try:
        _ = file.write_text(response.create_report(exc), "utf8")
    except OSError as e:
        logger.warning(f"Unable to write response from {url} to disk ({e!r})")
    else:
        logger.debug(f"Saved response from {url} to '{file}'")


def _prepare_resp_file(folder: Path, url: AbsoluteHttpURL, created_at: datetime.datetime, ext: str = ".html") -> Path:
    max_stem_len = 245 - len(str(folder)) + len(constants.STARTUP_TIME_STR) + 10
    log_date = created_at.strftime(constants.LOGS_DATETIME_FORMAT)
    path_safe_url = sanitize_filename(Path(str(url)).as_posix().replace("/", "-"))
    filename = f"{path_safe_url[:max_stem_len]}_{log_date}{ext}"
    return folder / filename
