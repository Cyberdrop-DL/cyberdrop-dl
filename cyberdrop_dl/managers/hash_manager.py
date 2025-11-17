from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

import xxhash

from cyberdrop_dl.clients.hash_client import HashClient

if TYPE_CHECKING:
    from cyberdrop_dl.managers.manager import Manager

_HASHERS: Final = {
    "md5": hashlib.md5,
    "xxh128": xxhash.xxh128,
    "sha256": hashlib.sha256,
}
_CHUNK_SIZE: Final = 1024 * 1024  # 1MB


class HashManager:
    def __init__(self, manager: Manager) -> None:
        self._cwd: Path = Path.cwd()
        self.hash_client: HashClient = HashClient(manager)

    async def hash_file(self, filename: Path | str, hash_type: Literal["xxh128", "md5", "sha256"]) -> str:
        file_path = self._cwd / filename
        return await asyncio.to_thread(_compute_hash, file_path, hash_type)


def _compute_hash(file: Path, algorithm: Literal["xxh128", "md5", "sha256"]) -> str:
    with file.open("rb") as file_io:
        hash = _HASHERS[algorithm]()
        buffer = bytearray(_CHUNK_SIZE)  # Reusable buffer to reduce allocations
        mem_view = memoryview(buffer)
        while size := file_io.readinto(buffer):
            hash.update(mem_view[:size])

    return hash.hexdigest()
