from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import sqlite3
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

import aiosqlite

from cyberdrop_dl.signature import dataclass_repr

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable
    from pathlib import Path

    from cyberdrop_dl.database._db import Database

logger = logging.getLogger(__name__)

MIN_FREE_SPACE = 50e6


@dataclass_repr("name", "_thread")
class DBConnection(aiosqlite.Connection):
    def __init__(
        self, connector: Callable[[], sqlite3.Connection], iter_chunk_size: int = 64, *, name: str | None = None
    ) -> None:
        super().__init__(connector, iter_chunk_size)
        self._name: str | None = name
        if name:
            self._thread._name = name  # pyright: ignore[reportAttributeAccessIssue]

    @property
    def name(self) -> str | None:
        return self._name


@dataclasses.dataclass(slots=True)
class Table(ABC):
    NAME: ClassVar[str]
    db: Database

    @property
    def ignore_history(self) -> bool:
        return self.db.ignore_history

    def __repr__(self) -> str:
        return f"<{type(self).__name__}(name={self.NAME!r})>"

    def __init_subclass__(cls, name: str | None = None) -> None:
        if name:
            cls.NAME = name

    @abstractmethod
    async def create(self) -> None: ...

    async def exists(self) -> bool:
        query = "SELECT 1 FROM sqlite_master WHERE type='table' AND name= ? LIMIT 1;"
        async with self.db.reader() as db_conn:
            cursor = await db_conn.execute(query, (self.NAME,))
            return await cursor.fetchone() is not None


async def raw_connect(path: Path, name: str | None = None) -> DBConnection:
    db_conn = DBConnection(lambda: sqlite3.connect(path, timeout=20), name=name)
    await db_conn
    db_conn.row_factory = aiosqlite.Row
    return db_conn


@contextlib.asynccontextmanager
async def connect(path: Path, name: str | None = None) -> AsyncGenerator[DBConnection]:
    db_conn = await raw_connect(path, name=name)
    try:
        yield db_conn
    finally:
        await db_conn.close()


async def unused_space(db_conn: aiosqlite.Connection) -> int:
    async def execute(query: str) -> int:
        cursor = await db_conn.execute(query)
        row = await cursor.fetchone()
        assert row is not None
        return int(row[0])

    free_pages, page_size = await asyncio.gather(execute("PRAGMA freelist_count;"), execute("PRAGMA page_size;"))  # noqa: TID251
    return free_pages * page_size


async def pre_allocate_250mb(db_conn: aiosqlite.Connection) -> None:
    """Pre-allocate SQL file just in case the user runs out of disk space."""

    if await unused_space(db_conn) > MIN_FREE_SPACE:
        return

    logger.debug("Database free rows are too low. Preallocating an additional 250MiB")
    script = "CREATE TABLE IF NOT EXISTS t(x);INSERT INTO t VALUES(zeroblob(250*1024*1024));DROP TABLE t;"
    await db_conn.executescript(script)
    await db_conn.commit()
