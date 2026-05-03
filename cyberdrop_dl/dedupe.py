from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from send2trash import send2trash

from cyberdrop_dl import aio
from cyberdrop_dl.progress.dedupe import DedupeStats, DedupeUI

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.database import Database
    from cyberdrop_dl.hasher import FileHashes

logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class Czkawka:
    base_dir: Path
    database: Database
    use_trash_bin: bool
    _sem: asyncio.BoundedSemaphore = dataclasses.field(init=False, default_factory=lambda: asyncio.BoundedSemaphore(20))
    _tui: DedupeUI = dataclasses.field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._tui = DedupeUI(self.base_dir)

    @property
    def stats(self) -> DedupeStats:
        return self._tui.stats

    async def run(self, file_hashes: FileHashes) -> None:
        with self._tui():
            await self.final_dupe_cleanup(file_hashes)

    async def final_dupe_cleanup(self, file_hashes: FileHashes) -> None:
        async with asyncio.TaskGroup() as tg:

            async def delete_dupes(hash_value: str, size: int) -> None:
                async with contextlib.aclosing(self._get_db_matches(hash_value, size)) as files:
                    async for file in files:
                        await self._sem.acquire()
                        tg.create_task(self._delete_and_log(file, hash_value))

            for hash_value, size_dict in file_hashes.items():
                for size in size_dict:
                    tg.create_task(delete_dupes(hash_value, size))

    async def _get_db_matches(self, hash_value: str, size: int) -> AsyncGenerator[Path]:
        get_matches = self.database.hash.get_files_with_hash_matches
        db_matches = await get_matches(hash_value, size, "xxh128")
        for row in db_matches[1:]:
            file = Path(row["folder"], row["download_filename"])
            if file.is_relative_to(self.base_dir):
                yield file

    async def _delete_and_log(self, file: Path, xxh128_value: str) -> None:
        hash_string = f"xxh128:{xxh128_value}"
        suffix = "Sent to trash" if self.use_trash_bin else "Permanently deleted"

        with self._tui.new_file(file):
            try:
                deleted = await _delete_file(file, self.use_trash_bin)
            except OSError as e:
                logger.exception(f"Unable to remove '{file}' ({hash_string}): {e}")

            else:
                if not deleted:
                    return

                msg = (
                    f"Removed new download '{file}' [{suffix}]. "
                    f"File hash matches with a previous download ({hash_string})"
                )
                logger.info(msg)
                self._tui.stats.deleted += 1

            finally:
                self._sem.release()


async def _delete_file(path: Path, to_trash: bool = True) -> bool:
    """Deletes a file and return `True` on success, `False` is the file was not found.

    Any other exception is propagated"""

    if to_trash:
        coro = asyncio.to_thread(send2trash, path)
    else:
        coro = aio.unlink(path)

    try:
        await coro
        return True
    except FileNotFoundError:
        pass
    except OSError as e:
        # send2trash raises everything as a bare OSError. We should only ignore FileNotFound and raise everything else
        msg = str(e)
        if "File not found" not in msg:
            raise

    return False
