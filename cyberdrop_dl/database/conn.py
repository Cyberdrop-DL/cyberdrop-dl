from __future__ import annotations

import contextlib
import functools
import logging
import sqlite3
from collections.abc import Generator, Sequence
from typing import TYPE_CHECKING, Any, Self, override

import aiosqlite
from aiosqlite.context import Result
from aiosqlite.core import Cursor

from cyberdrop_dl import env
from cyberdrop_dl.signature import dataclass_repr

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from pathlib import Path


type _SqliteData = str | int | float | None
type _Parameters = Sequence[_SqliteData] | dict[str, _SqliteData]


logger = logging.getLogger(__name__)


def _typed_contextmanager[**P, T](method: Callable[P, Coroutine[Any, Any, T]]) -> Callable[P, Result[T]]:
    @functools.wraps(method)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Result[T]:
        return Result(method(*args, **kwargs))

    return wrapper


@dataclass_repr("name", "_thread")
class DBConnection(aiosqlite.Connection):
    """A connection that autocloses throwaway cursors on the worker thread call

    It also fixes some typing issues"""

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

    if TYPE_CHECKING:

        @override
        async def _execute[**P, T](self, fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T: ...

        @override
        async def create_function(
            self, name: str, num_params: int, func: Callable[..., Any], deterministic: bool = False
        ) -> None: ...

        @override
        def __await__(self) -> Generator[Any, None, Self]: ...

    @override
    @_typed_contextmanager
    async def cursor(self) -> Cursor:
        return Cursor(self, await self._execute(self._conn.cursor))

    async def execute_and_close(self, sql: str, parameters: _Parameters | None = None) -> sqlite3.Cursor:
        if parameters is None:
            parameters = []
        return await self._execute(self._execute_and_close, sql, parameters)

    def _execute_and_close(self, sql: str, parameters: _Parameters) -> sqlite3.Cursor:
        with contextlib.closing(self._conn.execute(sql, parameters)) as cursor:
            return cursor

    @override
    def _execute_insert(self, sql: str, parameters: _Parameters) -> sqlite3.Row | None:
        with contextlib.closing(self._conn.execute(sql, parameters)) as cursor:
            cursor.execute("SELECT last_insert_rowid()")
            return cursor.fetchone()

    @override
    def _execute_fetchall(self, sql: str, parameters: _Parameters) -> list[sqlite3.Row]:
        with contextlib.closing(self._conn.execute(sql, parameters)) as cursor:
            return cursor.fetchall()

    def _execute_fetchone(self, sql: str, parameters: _Parameters) -> sqlite3.Row | None:
        with contextlib.closing(self._conn.execute(sql, parameters)) as cursor:
            return cursor.fetchone()

    def _execute_and_check(self, sql: str, parameters: _Parameters) -> bool:
        with contextlib.closing(self._conn.execute(sql, parameters)) as cursor:
            return cursor.fetchone() is not None

    @override
    @_typed_contextmanager
    async def execute_fetchone(self, sql: str, parameters: _Parameters | None = None) -> sqlite3.Row | None:
        if parameters is None:
            parameters = []
        return await self._execute(self._execute_fetchone, sql, parameters)

    @override
    @_typed_contextmanager
    async def execute_fetchall(self, sql: str, parameters: _Parameters | None = None) -> list[sqlite3.Row]:  # pyright: ignore[reportIncompatibleMethodOverride]
        if parameters is None:
            parameters = []
        return await self._execute(self._execute_fetchall, sql, parameters)

    @_typed_contextmanager
    async def execute_and_check(self, sql: str, parameters: _Parameters | None = None) -> bool:
        if parameters is None:
            parameters = []
        return await self._execute(self._execute_and_check, sql, parameters)


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
