from __future__ import annotations

import asyncio
import csv
import dataclasses
import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Self

from cyberdrop_dl.exceptions import get_origin
from cyberdrop_dl.logs import log_spacer
from cyberdrop_dl.utils import json

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path

    from yarl import URL

    from cyberdrop_dl.manager import Manager
    from cyberdrop_dl.url_objects import MediaItem


logger = logging.getLogger(__name__)

_CSV_DELIMITER = ","


@dataclasses.dataclass(slots=True, kw_only=True)
class CSVFiles:
    main_log: Path
    last_post_log: Path
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

    @classmethod
    def from_manager(cls, manager: Manager) -> Self:
        files = CSVFiles(
            main_log=manager.config.settings.logs.main_log,
            last_post_log=manager.config.settings.logs.last_forum_post,
            unsupported_urls_log=manager.config.settings.logs.unsupported_urls,
            download_error_log=manager.config.settings.logs.download_error_urls,
            scrape_error_log=manager.config.settings.logs.scrape_error_urls,
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

    def write_last_post_log(self, url: URL) -> None:
        """Writes to the last post log."""
        _ = self.task_group.create_task(self._write_to_csv(self.files.last_post_log, url=url))

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

    async def update_last_forum_post(self, input_file: Path) -> None:
        """Updates the last forum post."""

        def update() -> None:
            if input_file.is_file() and self.files.last_post_log.is_file():
                _update_last_forum_post(input_file, self.files.last_post_log)

        await asyncio.to_thread(update)


def _update_last_forum_post(input_file: Path, last_post_log: Path) -> None:
    log_spacer()
    logger.info("Updating Last Forum Posts...\n")

    current_urls, current_base_urls, new_urls, new_base_urls = [], [], [], []
    try:
        with input_file.open(encoding="utf8") as f:
            for line in f:
                url = base_url = line.strip().removesuffix("/")

                if "https" in url and "/post-" in url:
                    base_url = url.rsplit("/post", 1)[0]

                # only keep 1 url of the same thread
                if base_url not in current_base_urls:
                    current_urls.append(url)
                    current_base_urls.append(base_url)

    except UnicodeDecodeError:
        logger.exception("Unable to read input file, skipping update_last_forum_post")
        return

    with last_post_log.open(encoding="utf8") as f:
        reader = csv.DictReader(f.readlines())
        for row in reader:
            new_url = base_url = row["url"].strip().removesuffix("/")  # type: ignore

            if "https" in new_url and "/post-" in new_url:
                base_url = new_url.rsplit("/post", 1)[0]

            # only keep 1 url of the same thread
            if base_url not in new_base_urls:
                new_urls.append(new_url)
                new_base_urls.append(base_url)

    updated_urls = current_urls.copy()
    for new_url, base in zip(new_urls, new_base_urls, strict=False):
        if base in current_base_urls:
            index = current_base_urls.index(base)
            old_url = current_urls[index]
            if old_url == new_url:
                continue
            logger.info(f"Updating {base}\n  {old_url = }\n  {new_url = }")
            updated_urls[index] = new_url

    if updated_urls == current_urls:
        logger.info("No URLs updated")
        return

    with input_file.open("w", encoding="utf8") as f:
        f.write("\n".join(updated_urls))
