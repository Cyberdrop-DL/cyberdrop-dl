from __future__ import annotations

import asyncio
import dataclasses
import logging
import sqlite3
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl import env
from cyberdrop_dl.database.conn import DBConnection

if TYPE_CHECKING:
    from pathlib import Path

    from cyberdrop_dl.database._db import Database

logger = logging.getLogger(__name__)

MIN_FREE_SPACE = 50e6


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


def _log_query(query: str, name: str | None = None) -> None:
    query = query.strip()
    if query.count("\n") > 1:
        query = "\n" + query
    if name:
        name = f"[{name}]"

    logger.debug("[SQL]%s executing: %s", name, query)


def _connect(path: Path, name: str | None) -> sqlite3.Connection:
    db_conn = sqlite3.connect(path, timeout=20)
    db_conn.row_factory = sqlite3.Row
    if env.DEBUG_MODE:
        db_conn.set_trace_callback(lambda query: _log_query(query, name))
    return db_conn


def connect(path: Path, name: str | None = None) -> DBConnection:
    return DBConnection(lambda: _connect(path, name), name=name)


async def unused_space(db_conn: DBConnection) -> int:
    async def execute(query: str) -> int:
        row = await db_conn.execute_fetchone(query)
        assert row is not None
        return int(row[0])

    free_pages, page_size = await asyncio.gather(execute("PRAGMA freelist_count;"), execute("PRAGMA page_size;"))  # noqa: TID251
    return free_pages * page_size


async def pre_allocate_250mb(db_conn: DBConnection) -> None:
    """Pre-allocate SQL file just in case the user runs out of disk space."""

    if await unused_space(db_conn) > MIN_FREE_SPACE:
        return

    logger.debug("Database free rows are too low. Preallocating an additional 250MiB")
    script = "CREATE TABLE IF NOT EXISTS t(x);INSERT INTO t VALUES(zeroblob(250*1024*1024));DROP TABLE t;"
    await (await db_conn.executescript(script)).close()
    await db_conn.commit()
