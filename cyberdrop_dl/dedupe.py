from __future__ import annotations

import asyncio
import dataclasses
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Self

import send2trash

from cyberdrop_dl import aio, csv_logs
from cyberdrop_dl.progress.dedupe import DedupeStats, DedupeUI

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Generator, Iterable

    from cyberdrop_dl.database import Database
    from cyberdrop_dl.hasher import FileHashes
    from cyberdrop_dl.manager import Manager

logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class Czkawka:
    base_dir: Path
    database: Database
    use_trash_bin: bool
    csv_file: Path
    _sem: asyncio.BoundedSemaphore = dataclasses.field(init=False, default_factory=lambda: asyncio.BoundedSemaphore(20))
    _tui: DedupeUI = dataclasses.field(init=False, repr=False)
    _removed: list[dict[str, Path | str]] = dataclasses.field(init=False, default_factory=list, repr=False)

    @classmethod
    def from_manager(cls, manager: Manager) -> Self:
        return cls(
            base_dir=manager.config.download_folder.expanduser().resolve().absolute(),
            database=manager.database,
            use_trash_bin=manager.config.hashing.dedupe.use_trash_bin,
            csv_file=manager.config.logs.files.dedupe,
        )

    def __post_init__(self) -> None:
        self._tui = DedupeUI(self.base_dir)

    @property
    def stats(self) -> DedupeStats:
        return self._tui.stats

    async def run(self, file_hashes: FileHashes) -> None:
        logger.info(f"Starting dedupe of new downloads in '{self.base_dir}'")
        with self._tui():
            await self._dedupe(file_hashes)

        if self._removed:
            await asyncio.to_thread(csv_logs.write_rows, self.csv_file, self._removed)
            logger.info(f"Saved the details of every deleted duplicate to '{self.csv_file}'")

        logger.info(f"Dedupe finished. Deleted {self.stats.deleted:,} of {self.stats.total:,} duplicates found")

    async def _dedupe(self, file_hashes: FileHashes) -> None:
        async with asyncio.TaskGroup() as tg:

            async def delete_dupes(hash_value: str, size: int, paths: set[Path]) -> None:
                db_matches = await self.database.hash.get_files_with_hash_matches(hash_value, size, "xxh128")
                for original, file in _filter_db_matches(db_matches, self.base_dir):
                    if file not in paths:
                        continue
                    await self._sem.acquire()
                    tg.create_task(self._delete_and_log(file, original, hash_value))

            for hash_value, sizes in file_hashes.items():
                for size, paths in sizes.items():
                    tg.create_task(delete_dupes(hash_value, size, paths))

    async def _delete_and_log(self, file: Path, original: Path, xxh128_value: str) -> None:
        hash_string = f"xxh128:{xxh128_value}"
        suffix = "Sent to trash" if self.use_trash_bin else "Permanently deleted"

        with self._tui.new_file(file):
            try:
                deleted = await _delete_file(file, to_trash=self.use_trash_bin)
            except OSError as e:
                logger.error(f"Unable to remove '{file}' ({hash_string}): {e!r}")

            else:
                if deleted:
                    logger.info(
                        f"Removed new download '{file}' [{suffix}]. It's a duplicate of '{original}' ({hash_string})"
                    )
                    self._tui.stats.deleted += 1
                    self._removed.append({"duplicate": file, "original": original, "hash": hash_string})

            finally:
                self._sem.release()


async def _delete_file(path: Path, *, to_trash: bool) -> bool:
    """Deletes a file and return `True` on success, `False` is the file was not found.

    Any other exception is propagated"""

    coro = asyncio.to_thread(send2trash.send2trash, path) if to_trash else aio.unlink(path)

    try:
        await coro
    except FileNotFoundError:
        return False
    except OSError as e:
        # send2trash raises everything as a bare OSError. We should only ignore FileNotFound and raise everything else
        if "file not found" in str(e).casefold():
            return False
        raise
    else:
        return True


def _filter_db_matches(db_matches: Iterable[sqlite3.Row], base_dir: Path) -> Generator[tuple[Path, Path]]:
    """Yields `(original, duplicate)` pairs.

    The original is the first row, AKA the first file ever downloaded with this hash. It's always kept,
    even if it's outside of `base_dir`."""

    rows = iter(db_matches)
    if (first := next(rows, None)) is None:
        return

    original = _row_path(first)
    for row in rows:
        file = _row_path(row)
        if file.is_relative_to(base_dir):
            yield original, file


def _row_path(row: sqlite3.Row) -> Path:
    return Path(row["folder"], row["download_filename"])
