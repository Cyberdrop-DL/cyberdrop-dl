from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import logging
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

import xxhash

from cyberdrop_dl import aio
from cyberdrop_dl.constants import Hashing, TempExt
from cyberdrop_dl.dedupe import Czkawka
from cyberdrop_dl.progress.hashing import HashingStats, HashingUI

if TYPE_CHECKING:
    from yarl import URL

    from cyberdrop_dl.config.settings import DupeCleanup
    from cyberdrop_dl.managers.manager import Manager
    from cyberdrop_dl.url_objects import MediaItem


_HASHERS: Final = {
    "md5": hashlib.md5,
    "xxh128": xxhash.xxh128,
    "sha256": hashlib.sha256,
}
_CHUNK_SIZE: Final = 1024 * 1024  # 1MB


logger = logging.getLogger(__name__)


def _compute_hash(file: Path, algorithm: Literal["xxh128", "md5", "sha256"]) -> str:
    with file.open("rb") as fp:
        hash = _HASHERS[algorithm]()
        buffer = bytearray(_CHUNK_SIZE)
        mem_view = memoryview(buffer)
        while size := fp.readinto(buffer):
            hash.update(mem_view[:size])

    return hash.hexdigest()


async def hash_directory_scanner(manager: Manager, path: Path) -> None:
    manager.async_db_hash_startup()
    async with manager.database:
        stats = await manager.hasher.hash_directory(path)

    manager.print_hashing_stats(stats)


@dataclasses.dataclass(slots=True)
class Hasher:
    manager: Manager
    hashed_media_items: list[MediaItem] = dataclasses.field(init=False, repr=False, default_factory=list)
    hashes_dict: dict[str, dict[int, set[Path]]] = dataclasses.field(
        init=False,
        repr=False,
        default_factory=lambda: defaultdict(lambda: defaultdict(set)),
    )
    _sem: asyncio.BoundedSemaphore = dataclasses.field(init=False, default_factory=lambda: asyncio.BoundedSemaphore(20))
    _cwd: Path = dataclasses.field(init=False, default_factory=Path.cwd)
    _hashed_items: set[tuple[str, ...]] = dataclasses.field(default_factory=set, repr=False)
    _tui: HashingUI = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self._tui = HashingUI(self.download_folder)

    @property
    def download_folder(self) -> Path:
        return self.manager.config.settings.files.download_folder.expanduser().resolve().absolute()

    @property
    def stats(self):
        return self._tui.stats

    @property
    def config(self) -> DupeCleanup:
        return self.manager.config.settings.dupe_cleanup_options

    async def hash_file(self, filename: Path | str, hash_type: Literal["xxh128", "md5", "sha256"]) -> str:
        file_path = self._cwd / filename
        return await asyncio.to_thread(_compute_hash, file_path, hash_type)

    async def hash_directory(self, path: Path) -> HashingStats:
        path = Path(path)
        tui = HashingUI(path)
        old_tui = self._tui
        with tui():
            if not await aio.is_dir(path):
                raise NotADirectoryError(None, path)

            try:
                self._tui = tui
                async with asyncio.TaskGroup() as tg:
                    async for file in aio.rglob(path, "*"):
                        _ = tg.create_task(self.update_db_and_retrive_hash(file))
            finally:
                self._tui = old_tui

        return tui.stats

    async def hash_item(self, media_item: MediaItem) -> None:
        if media_item.is_segment:
            return
        hash = await self.update_db_and_retrive_hash(media_item.path, media_item.original_filename, media_item.referer)
        await self.save_hash_data(media_item, hash)

    async def hash_item_during_download(self, media_item: MediaItem) -> None:
        if media_item.is_segment:
            return

        if self.config.hashing != Hashing.IN_PLACE:
            return

        try:
            assert media_item.original_filename
            hash = await self.update_db_and_retrive_hash(
                media_item.path, media_item.original_filename, media_item.referer
            )
            await self.save_hash_data(media_item, hash)
        except Exception as e:
            logger.exception(f"After hash processing failed: '{media_item.path}' with error {e}")

    async def update_db_and_retrive_hash(
        self,
        file: Path | str,
        original_filename: str | None = None,
        referer: URL | None = None,
    ) -> str | None:
        file = Path(file)

        if file.suffix in TempExt:
            return

        try:
            if not await aio.get_size(file):
                return
        except IsADirectoryError:
            return

        async with self._sem:
            with self._tui.new_file(file):
                async with asyncio.TaskGroup() as tg:
                    logger.info("Computing hashes of '%s'", file)
                    hash = tg.create_task(self._update_db_and_retrive_hash(file, original_filename, referer, "xxh128"))
                    if self.config.add_md5_hash:
                        tg.create_task(self._update_db_and_retrive_hash(file, original_filename, referer, "md5"))
                    if self.config.add_sha256_hash:
                        tg.create_task(self._update_db_and_retrive_hash(file, original_filename, referer, "sha256"))

        return hash.result()

    async def _update_db_and_retrive_hash(
        self,
        file: Path,
        original_filename: str | None,
        referer: URL | None,
        hash_type: Literal["xxh128", "md5", "sha256"],
    ) -> str | None:
        """Generates hash of a file."""

        hash = await self.manager.database.hash.get_file_hash_exists(file, hash_type)
        try:
            if not hash:
                hash = await self.hash_file(file, hash_type)
                await self.manager.database.hash.insert_or_update_hash_db(
                    hash,
                    hash_type,
                    file,
                    original_filename,
                    referer,
                )
                self._tui.add_completed(hash_type)
            else:
                self._tui.stats.prev_hashed += 1
                await self.manager.database.hash.insert_or_update_hash_db(
                    hash,
                    hash_type,
                    file,
                    original_filename,
                    referer,
                )
        except Exception as e:
            logger.exception(f"Error hashing '{file}' : {e}")
        else:
            return hash

    async def save_hash_data(self, media_item: MediaItem, hash: str | None) -> None:
        if not hash:
            return

        absolute_path = await aio.resolve(media_item.path)
        size = await aio.get_size(media_item.path)
        assert size
        self.hashed_media_items.append(media_item)
        if hash:
            media_item.hash = hash
        self.hashes_dict[hash][size].add(absolute_path)
        self._hashed_items.add(media_item.id)

    async def cleanup_dupes_after_download(self) -> None:
        if self.config.hashing == Hashing.OFF:
            return
        if not self.config.auto_dedupe:
            return
        if self.manager.config.settings.runtime_options.ignore_history:
            return
        with self._tui():
            file_hashes_dict = await self.get_file_hashes_dict()

        deduper = Czkawka(self.download_folder, self.manager.database, use_trash_bin=self.config.send_deleted_to_trash)
        await deduper.run(file_hashes_dict)

    async def get_file_hashes_dict(self) -> dict[str, dict[int, set[Path]]]:

        async def exists(item: MediaItem) -> MediaItem | None:
            if await aio.is_file(item.path):
                return item

        results = await asyncio.gather(
            *(exists(item) for item in self.manager.completed_downloads if item.id not in self._hashed_items)
        )
        for media_item in results:
            if media_item is None:
                continue
            try:
                await self.hash_item(media_item)
            except Exception:
                logger.exception(msg=f"Unable to hash '{media_item.path}'")
        return self.hashes_dict
