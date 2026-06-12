from __future__ import annotations

import contextlib
import dataclasses
from typing import TYPE_CHECKING, Self

import aiosqlite

from cyberdrop_dl import aio
from cyberdrop_dl.database.hash import HashTable
from cyberdrop_dl.database.history import HistoryTable
from cyberdrop_dl.database.schema import SchemaTable

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path


async def _connect(path: Path) -> aiosqlite.Connection:
    db_conn = await aiosqlite.connect(path, timeout=20)
    db_conn.row_factory = aiosqlite.Row
    return db_conn


@contextlib.asynccontextmanager
async def connect(path: Path) -> AsyncGenerator[aiosqlite.Connection]:
    db_conn = await _connect(path)
    try:
        yield db_conn
    finally:
        await db_conn.close()


@dataclasses.dataclass(slots=True)
class Database:
    path: Path
    ignore_history: bool = False

    history: HistoryTable = dataclasses.field(init=False)
    hash: HashTable = dataclasses.field(init=False)
    schema: SchemaTable = dataclasses.field(init=False)

    _conn: aiosqlite.Connection = dataclasses.field(init=False)
    _is_new: bool = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self.history = HistoryTable(self)
        self.hash = HashTable(self)
        self.schema = SchemaTable(self)

    @property
    def conn(self) -> aiosqlite.Connection:
        return self._conn

    async def _connect(self) -> None:
        self._is_new = not await aio.get_size(self.path)
        self._conn = await _connect(self.path)

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncGenerator[Self]:
        await self._connect()
        try:
            yield self
        finally:
            await self.conn.close()

    async def _create_tables(self) -> None:
        await self.schema.create()
        if not self._is_new:
            self.schema.check_version()
        await pre_allocate_100mb(self.conn)
        await self.history.create()
        await self.hash.create()
        if self._is_new:
            await self.schema.update()

    async def create_tables(self) -> None:
        try:
            await self._create_tables()
        except Exception:
            if self._is_new:
                await self.conn.close()
                try:
                    await aio.unlink(self.path, missing_ok=True)
                except OSError:
                    pass
            raise
        else:
            if not (self._is_new or self.schema.up_to_date):
                await self.history.apply_updates()
                await self.schema.update()

    async def __aenter__(self) -> Self:
        await self._connect()
        await self.create_tables()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.conn.close()


async def pre_allocate_100mb(db_conn: aiosqlite.Connection) -> None:
    """Pre-allocate 100MB of space to the SQL file just in case the user runs out of disk space."""

    cursor = await db_conn.execute("PRAGMA freelist_count;")
    free_space = await cursor.fetchone()
    assert free_space is not None

    if free_space[0] > 1024:
        return

    pre_allocate_script = (
        "CREATE TABLE IF NOT EXISTS t(x);"
        "INSERT INTO t VALUES(zeroblob(100*1024*1024));"  # 100 MB
        "DROP TABLE t;"
    )
    _ = await db_conn.executescript(pre_allocate_script)
    await db_conn.commit()
