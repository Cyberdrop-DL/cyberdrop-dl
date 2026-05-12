from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, Self

import aiosqlite

from .tables import HashTable, HistoryTable, SchemaVersionTable

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


async def connect(path: Path) -> aiosqlite.Connection:
    db_conn = await aiosqlite.connect(path, timeout=20)
    db_conn.row_factory = aiosqlite.Row
    return db_conn


@dataclasses.dataclass(slots=True)
class Database:
    _db_path: Path
    ignore_history: bool

    history: HistoryTable = dataclasses.field(init=False)
    hash: HashTable = dataclasses.field(init=False)
    schema: SchemaVersionTable = dataclasses.field(init=False)
    _db_conn: aiosqlite.Connection = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self.history = HistoryTable(self)
        self.hash = HashTable(self)
        self.schema = SchemaVersionTable(self)

    async def __aenter__(self) -> Self:
        self._db_conn = await connect(self._db_path)
        await self._pre_allocate()
        await self.history.create()
        await self.hash.create()
        await self.schema.create()
        return self

    async def fetchone(self, query: str, parameters: Iterable[Any] | None = None) -> aiosqlite.Row | None:
        cursor = await self._db_conn.execute(query, parameters)
        return await cursor.fetchone()

    async def fetchall(self, query: str, parameters: Iterable[Any] | None = None) -> list[aiosqlite.Row]:
        return await self._db_conn.execute_fetchall(query, parameters)  # pyright: ignore[reportReturnType]

    async def __aexit__(self, *_) -> None:
        await self._db_conn.close()

    async def _pre_allocate(self) -> None:
        """We pre-allocate 100MB of space to the SQL file just in case the user runs out of disk space."""

        free_space = await self.fetchone("PRAGMA freelist_count;")
        assert free_space is not None

        if free_space[0] > 1024:
            return

        pre_allocate_script = (
            "CREATE TABLE IF NOT EXISTS t(x);"
            "INSERT INTO t VALUES(zeroblob(100*1024*1024));"  # 100 MB
            "DROP TABLE t;"
        )
        _ = await self._db_conn.executescript(pre_allocate_script)
        await self._db_conn.commit()


__all__ = ["Database"]
