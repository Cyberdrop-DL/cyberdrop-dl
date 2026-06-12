from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

    from cyberdrop_dl.database import Database


@dataclasses.dataclass(slots=True)
class Table(ABC):
    _database: Database = dataclasses.field(repr=False)

    @property
    def db_conn(self) -> aiosqlite.Connection:
        return self._database.conn

    @abstractmethod
    async def create(self) -> None: ...


async def exists(db_conn: aiosqlite.Connection, table: str) -> bool:
    query = "SELECT 1 FROM sqlite_master WHERE type='table' AND name= ? ;"
    cursor = await db_conn.execute(query, (table,))
    return await cursor.fetchone() is not None
