from __future__ import annotations

import contextlib
import functools
import sqlite3
from typing import TYPE_CHECKING, Any, Concatenate, Protocol, overload

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    import aiosqlite


class ConnectionAwareCallable[**P, T](Protocol):
    @overload
    def __call__(self, conn: sqlite3.Connection, *args: P.args, **kwargs: P.kwargs) -> T: ...

    @overload
    def __call__(self, conn: aiosqlite.Connection, *args: P.args, **kwargs: P.kwargs) -> Coroutine[Any, Any, T]: ...

    def __call__(
        self, conn: sqlite3.Connection | aiosqlite.Connection, *args: P.args, **kwargs: P.kwargs
    ) -> Coroutine[Any, Any, T] | T: ...


def make_conn_aware[**P, T](fn: Callable[Concatenate[sqlite3.Connection, P], T]) -> ConnectionAwareCallable[P, T]:
    """Adapt a synchronous SQLite callable to work with both sync and async connections.

    When given an aiosqlite.Connection, it runs the function in aiosqlite's worker thread.

    NOTE: The wrapped function SHOULD NOT return any object that depends on the connection remaining open (ex: cursors)
    """

    @functools.wraps(fn)
    def wrapper(
        conn: sqlite3.Connection | aiosqlite.Connection, *args: P.args, **kwargs: P.kwargs
    ) -> T | Coroutine[Any, Any, T]:
        if isinstance(conn, sqlite3.Connection):
            return fn(conn, *args, **kwargs)

        @functools.wraps(fn)
        def run() -> T:
            return fn(conn._conn, *args, **kwargs)

        return conn._execute(run)

    return wrapper  # pyright: ignore[reportReturnType]


@make_conn_aware
def get_column_names(conn: sqlite3.Connection, table: str, schema: str = "main") -> set[str]:
    with contextlib.closing(conn.execute(f"PRAGMA {schema}.table_info({table})")) as cursor:
        return {r[1] for r in cursor.fetchall()}
