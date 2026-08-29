from __future__ import annotations

import contextlib
import dataclasses
import sqlite3
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

import aiosqlite

from cyberdrop_dl.signature import simple_repr

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable
    from pathlib import Path

    from cyberdrop_dl.database._db import Database


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

    __repr__ = simple_repr("name", "_thread")


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
