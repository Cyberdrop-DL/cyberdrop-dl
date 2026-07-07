from __future__ import annotations

import contextlib
import dataclasses
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

import aiosqlite

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path


@dataclasses.dataclass(slots=True)
class Table(ABC):
    NAME: ClassVar[str]
    db_conn: aiosqlite.Connection
    ignore_history: bool = False

    def __init_subclass__(cls, name: str | None = None) -> None:
        if name:
            cls.NAME = name

    @abstractmethod
    async def create(self) -> None: ...

    async def exists(self) -> bool:
        query = "SELECT 1 FROM sqlite_master WHERE type='table' AND name= ? LIMIT 1;"
        cursor = await self.db_conn.execute(query, (self.NAME,))
        return await cursor.fetchone() is not None


async def raw_connect(path: Path) -> aiosqlite.Connection:
    db_conn = await aiosqlite.connect(path, timeout=20)
    db_conn.row_factory = aiosqlite.Row
    return db_conn


@contextlib.asynccontextmanager
async def connect(path: Path) -> AsyncGenerator[aiosqlite.Connection]:
    db_conn = await raw_connect(path)
    try:
        yield db_conn
    finally:
        await db_conn.close()


async def pre_allocate_250mb(db_conn: aiosqlite.Connection) -> None:
    """Pre-allocate 250MB of space to the SQL file just in case the user runs out of disk space."""

    cursor = await db_conn.execute("PRAGMA freelist_count;")
    free_space = await cursor.fetchone()
    assert free_space is not None

    if free_space[0] > 1024:
        return

    pre_allocate_script = (
        "CREATE TABLE IF NOT EXISTS t(x);"
        "INSERT INTO t VALUES(zeroblob(250*1024*1024));"  # 250 MiB
        "DROP TABLE t;"
    )
    _ = await db_conn.executescript(pre_allocate_script)
    await db_conn.commit()
