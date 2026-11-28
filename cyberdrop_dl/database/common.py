from __future__ import annotations

import contextlib
import dataclasses
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, LiteralString

from cyberdrop_dl.database import make_conn_aware

if TYPE_CHECKING:
    import sqlite3

    from cyberdrop_dl.database.pool import PoolManager

logger = logging.getLogger(__name__)

MIN_FREE_SPACE = 50e6


@dataclasses.dataclass(slots=True)
class Table(ABC):
    NAME: ClassVar[str]
    db: PoolManager
    ignore_history: bool

    def __repr__(self) -> str:
        return f"<{type(self).__name__}(name={self.NAME!r})>"

    def __init_subclass__(cls, name: str | None = None) -> None:
        if name:
            cls.NAME = name

    @abstractmethod
    async def create(self) -> None: ...

    async def exists(self) -> bool:
        async with self.db.reader() as db_conn:
            return await check_table_exists(db_conn, self.NAME)


@make_conn_aware
def check_table_exists(db_conn: sqlite3.Connection, name: str) -> bool:
    query = "SELECT 1 FROM sqlite_master WHERE type='table' AND name= ? LIMIT 1;"
    with contextlib.closing(db_conn.execute(query, (name,))) as cursor:
        return cursor.fetchone() is not None


@make_conn_aware
def unused_space(db_conn: sqlite3.Connection) -> int:
    with contextlib.closing(db_conn.execute("PRAGMA freelist_count;")) as cursor:
        free_pages: int = cursor.fetchone()[0]
        page_size: int = cursor.execute("PRAGMA page_size;").fetchone()[0]

    return free_pages * page_size


@make_conn_aware
def pre_allocate_250mb(db_conn: sqlite3.Connection) -> None:
    """Pre-allocate SQL file just in case the user runs out of disk space."""

    if unused_space(db_conn) > MIN_FREE_SPACE:
        return

    logger.debug("Database free rows are too low. Preallocating an additional 250MiB")
    script = "CREATE TABLE IF NOT EXISTS t(x);INSERT INTO t VALUES(zeroblob(250*1024*1024));DROP TABLE t;"
    db_conn.executescript(script).close()
    db_conn.commit()


@make_conn_aware
def get_table_names(conn: sqlite3.Connection, schema: LiteralString = "main") -> set[str]:
    with contextlib.closing(conn.execute(f"SELECT name FROM {schema}.sqlite_master WHERE type='table'")) as cursor:  # noqa: S608
        return {r[0] for r in cursor.fetchall()}


@make_conn_aware
def get_column_names(conn: sqlite3.Connection, table: str, schema: str = "main") -> set[str]:
    with contextlib.closing(conn.execute(f"PRAGMA {schema}.table_info({table})")) as cursor:
        return {r[1] for r in cursor.fetchall()}
