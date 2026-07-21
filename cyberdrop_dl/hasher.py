from __future__ import annotations

import asyncio
import dataclasses
import hashlib
import logging
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, Self

import xxhash

from cyberdrop_dl import aio
from cyberdrop_dl.constants import TempExt
from cyberdrop_dl.progress.hashing import HashingStats, HashingUI

if TYPE_CHECKING:
    from collections.abc import Iterable

    from cyberdrop_dl.config import Config
    from cyberdrop_dl.database._db import Database
    from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem

FileHashes = dict[str, dict[int, set[Path]]]

_HASHERS: Final = {
    "md5": hashlib.md5,
    "xxh128": xxhash.xxh128,
    "sha256": hashlib.sha256,
}
_CHUNK_SIZE: Final = 1024 * 1024  # 1MB


logger = logging.getLogger(__name__)


def _compute_hash(file: Path, algorithm: Literal["xxh128", "md5", "sha256"]) -> str:
    with file.open("rb") as fp:
        hasher = _HASHERS[algorithm]()
        buffer = bytearray(_CHUNK_SIZE)
        mem_view = memoryview(buffer)
        while size := fp.readinto(buffer):
            hasher.update(mem_view[:size])

    return hasher.hexdigest()


async def hash_directory(hasher: Hasher) -> HashingStats:
    if not await aio.is_dir(hasher.path):
        raise NotADirectoryError(None, hasher.path)

    async with hasher.database:
        with hasher.tui():
            async with asyncio.TaskGroup() as tg:
                async for file in aio.rglob(hasher.path, "*"):
                    _ = tg.create_task(hasher.update_db_and_retrive_hash(file))

    return hasher.stats


@dataclasses.dataclass(slots=True)
class Hasher:
    extra_hashes: tuple[Literal["md5", "sha256"], ...]
    database: Database
    path: Path
    tui: HashingUI = dataclasses.field(init=False, repr=False)

    _cwd: Path = dataclasses.field(init=False, default_factory=Path.cwd)
    _hashes_map: FileHashes = dataclasses.field(
        init=False,
        repr=False,
        default_factory=lambda: defaultdict(lambda: defaultdict(set)),
    )
    _sem: asyncio.BoundedSemaphore = dataclasses.field(
        init=False,
        repr=False,
        default_factory=lambda: asyncio.BoundedSemaphore(20),
    )
    _hashed_items: set[tuple[str, ...]] = dataclasses.field(
        init=False,
        repr=False,
        default_factory=set,
    )

    def __post_init__(self) -> None:
        self.tui = HashingUI(self.path)

    @classmethod
    def create(cls, config: Config, db: Database, path: Path | None = None) -> Self:
        return cls(
            config.hashing.extra_hashes,
            db,
            path=(path or config.download_folder).expanduser().resolve().absolute(),
        )

    @property
    def stats(self) -> HashingStats:
        return self.tui.stats

    async def hash_file(self, filename: Path | str, hash_type: Literal["xxh128", "md5", "sha256"]) -> str:
        file_path = self._cwd / filename
        return await asyncio.to_thread(_compute_hash, file_path, hash_type)

    async def hash_item(self, media_item: MediaItem) -> None:
        if media_item.is_segment:
            return
        hash_value = await self.update_db_and_retrive_hash(
            media_item.path,
            media_item.original_filename,
            referer=media_item.referer,
        )
        await self.save_hash_data(media_item, hash_value)

    async def update_db_and_retrive_hash(
        self,
        file: Path | str,
        original_filename: str | None = None,
        referer: AbsoluteHttpURL | None = None,
    ) -> str | None:
        file = Path(file)

        if file.suffix in TempExt:
            return None

        try:
            if not await aio.get_size(file):
                return None
        except IsADirectoryError:
            return None

        hashes: dict[str, asyncio.Task[str | None]] = {}

        def compute_hash(algo: Literal["xxh128", "md5", "sha256"]) -> asyncio.Task[str | None]:
            hashes[algo] = task = tg.create_task(
                self._update_db_and_retrive_hash(file, original_filename, referer, algo)
            )
            return task

        async with self._sem:
            with self.tui.new_file(file):
                async with asyncio.TaskGroup() as tg:
                    logger.info("Computing hashes of '%s'", file)
                    xxxhash = compute_hash("xxh128")
                    for algo in self.extra_hashes:
                        _ = compute_hash(algo)

            logger.debug(
                "hashes of '%s'\n%s",
                file,
                {algo: result for algo, task in hashes.items() if (result := task.result()) is not None},
            )

        return xxxhash.result()

    async def _update_db_and_retrive_hash(
        self,
        file: Path,
        original_filename: str | None,
        referer: AbsoluteHttpURL | None,
        hash_type: Literal["xxh128", "md5", "sha256"],
    ) -> str | None:
        """Generates hash of a file."""

        hash_value = await self.database.hash.get_file_hash_exists(file, hash_type)
        try:
            if not hash_value:
                hash_value = await self.hash_file(file, hash_type)
                await self.database.hash.insert_or_update_hash_db(
                    hash_value,
                    hash_type,
                    file,
                    original_filename,
                    referer,
                )
                self.tui.add_completed(hash_type)
            else:
                self.tui.stats.prev_hashed += 1
                await self.database.hash.insert_or_update_hash_db(
                    hash_value,
                    hash_type,
                    file,
                    original_filename,
                    referer,
                )
        except Exception:
            logger.exception("Error hashing '%s'", file)
        else:
            return hash_value

    async def save_hash_data(self, media_item: MediaItem, hash_value: str | None) -> None:
        if not hash_value:
            return

        absolute_path = await aio.resolve(media_item.path)
        size = await aio.get_size(media_item.path)
        assert size
        if hash_value:
            media_item.xxhash = hash_value
        self._hashes_map[hash_value][size].add(absolute_path)
        self._hashed_items.add(media_item.id)

    async def run(self, downloads: Iterable[MediaItem]) -> FileHashes:
        with self.tui():
            return await self._get_file_hashes_dict(downloads)

    async def _get_file_hashes_dict(self, downloads: Iterable[MediaItem]) -> FileHashes:

        results = await aio.gather(*(_exists(item) for item in downloads if item.id not in self._hashed_items))
        for media_item in results:
            if media_item is None:
                continue
            try:
                await self.hash_item(media_item)
            except Exception:
                logger.exception(msg=f"Unable to hash '{media_item.path}'")
        return self._hashes_map


async def _exists(item: MediaItem) -> MediaItem | None:
    if await aio.is_file(item.path):
        return item


async def compute_in_place_hash(hasher: Hasher, media_item: MediaItem) -> None:
    try:
        assert media_item.original_filename
        hash_value = await hasher.update_db_and_retrive_hash(
            media_item.path, media_item.original_filename, media_item.referer
        )
        await hasher.save_hash_data(media_item, hash_value)
    except Exception:
        logger.exception("After hash processing failed: '%s'", media_item.path)
