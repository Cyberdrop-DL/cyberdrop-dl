from __future__ import annotations

import contextlib
import dataclasses
from typing import TYPE_CHECKING, Any, Self

import aiosqlite

from cyberdrop_dl import aio

from .tables import HashTable, HistoryTable, SchemaVersionTable

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterable
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
    _db_path: Path
    ignore_history: bool = False

    history: HistoryTable = dataclasses.field(init=False)
    hash: HashTable = dataclasses.field(init=False)
    schema: SchemaVersionTable = dataclasses.field(init=False)
    _conn: aiosqlite.Connection = dataclasses.field(init=False)
    _is_new: bool = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self.history = HistoryTable(self)
        self.hash = HashTable(self)
        self.schema = SchemaVersionTable(self)

    @property
    def conn(self) -> aiosqlite.Connection:
        return self._conn

    async def _connect(self) -> None:
        self._is_new = not await aio.get_size(self._db_path)
        self._conn = await _connect(self._db_path)

    async def exists(self, table: str) -> bool:
        query = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';"  # noqa: S608
        row = await self.fetchone(query)
        return row is not None

    async def _create_tables(self) -> None:
        await self.schema.create()
        if not self._is_new:
            self.schema.check_version()
        await _pre_allocate(self.conn)
        await self.history.create()
        await self.hash.create()
        if self._is_new:
            await self.schema.update()

    async def __aenter__(self) -> Self:
        await self._connect()
        try:
            await self._create_tables()
        except Exception:
            if self._is_new:
                await self.conn.close()
                try:
                    await aio.unlink(self._db_path, missing_ok=True)
                except OSError:
                    pass
            raise
        else:
            if not (self._is_new or self.schema.up_to_date):
                await self.history.apply_updates()
                await self.schema.update()

        return self

    async def fetchone(self, query: str, parameters: Iterable[Any] | None = None) -> aiosqlite.Row | None:
        cursor = await self.conn.execute(query, parameters)
        return await cursor.fetchone()

    async def fetchall(self, query: str, parameters: Iterable[Any] | None = None) -> list[aiosqlite.Row]:
        return await self.conn.execute_fetchall(query, parameters)  # pyright: ignore[reportReturnType]

    async def __aexit__(self, *_: object) -> None:
        await self.conn.close()


async def _pre_allocate(db_conn: aiosqlite.Connection) -> None:
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


__all__ = ["Database"]
