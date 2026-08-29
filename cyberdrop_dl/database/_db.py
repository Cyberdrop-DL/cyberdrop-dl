from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any, Self

from cyberdrop_dl import aio
from cyberdrop_dl.signature import simple_repr

from .common import connect, pre_allocate_250mb, raw_connect
from .hash import HashTable
from .history import HistoryTable
from .schema import SchemaTable

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    import aiosqlite


READ_POOL_SIZE = 10


def _current_task() -> asyncio.Task[Any]:
    task = asyncio.current_task()
    assert task is not None
    return task


class DBReadConnPool:
    def __init__(self, path: Path, size: int) -> None:
        self.path: Path = path
        self.max_size: int = size
        self._queue: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue(size)
        self._busy: dict[asyncio.Task[Any], aiosqlite.Connection] = {}
        self._stack: contextlib.AsyncExitStack = contextlib.AsyncExitStack()

    async def _new_conn(self, idx: int) -> None:
        conn = await self._stack.enter_async_context(connect(self.path, name=f"db-reader-{idx}"))
        await conn.execute("pragma query_only")
        self._queue.put_nowait(conn)

    async def init(self) -> None:
        await self._stack.__aenter__()
        async with asyncio.TaskGroup() as tg:
            for idx in range(self.max_size):
                tg.create_task(self._new_conn(idx))

    async def aclose(self) -> None:
        await self._stack.__aexit__(None, None, None)
        while True:
            try:
                _ = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    @contextlib.asynccontextmanager
    async def __call__(self) -> AsyncGenerator[aiosqlite.Connection]:
        task = _current_task()
        if (conn := self._busy.get(task)) is not None:
            yield conn
            return

        conn = self._busy[task] = await self._queue.get()
        try:
            yield conn
        finally:
            del self._busy[task]
            self._queue.put_nowait(conn)


class Database:
    def __init__(self, path: Path, ignore_history: bool = False) -> None:  # noqa: FBT001, FBT002
        self.path: Path = path
        self.ignore_history: bool = ignore_history
        self._pool: DBReadConnPool | None = None
        self._writer_task: asyncio.Task[Any] | None = None
        self._write_lock: asyncio.Lock = asyncio.Lock()

        self.history: HistoryTable = HistoryTable(self)
        self.hash: HashTable = HashTable(self)
        self.schema: SchemaTable = SchemaTable(self)

        self.conn: aiosqlite.Connection
        self.is_new: bool

    __repr__ = simple_repr("path", "ignore_history")

    async def _connect(self) -> None:
        self.is_new = not await aio.get_size(self.path)
        self.conn = await raw_connect(self.path, "db-writer")

    @contextlib.asynccontextmanager
    async def writer(self) -> AsyncGenerator[aiosqlite.Connection]:
        task = _current_task()
        if self._writer_task == task:
            yield self.conn
            return

        async with self._write_lock:
            self._writer_task = task
            try:
                yield self.conn
            finally:
                self._writer_task = None

    @contextlib.asynccontextmanager
    async def reader(self) -> AsyncGenerator[aiosqlite.Connection]:
        if not self._pool or _current_task() == self._writer_task:
            yield self.conn
            return

        async with self._pool() as conn:
            if conn.in_transaction:
                yield conn
                return

            await conn.execute("BEGIN DEFERRED;")
            try:
                yield conn
            finally:
                await conn.rollback()

    @contextlib.asynccontextmanager
    async def connect(self) -> AsyncGenerator[Self]:
        await self._connect()
        try:
            yield self
        finally:
            await self.conn.close()

    async def _create_tables(self) -> None:
        await self.schema.create()
        if not self.is_new:
            self.schema.check_version()
        await pre_allocate_250mb(self.conn)
        await self.history.create()
        await self.hash.create()
        if self.is_new:
            await self.schema.update()

    async def create_tables(self) -> None:
        try:
            await self._create_tables()
        except Exception:
            await self.conn.close()
            if self.is_new:
                try:
                    await aio.unlink(self.path, missing_ok=True)
                except OSError:
                    pass
            raise
        else:
            if not (self.is_new or self.schema.up_to_date):
                await self.history.apply_updates()
                await self.schema.update()

    async def __aenter__(self) -> Self:
        await self._connect()
        await (await self.conn.execute("pragma journal_mode=WAL")).close()
        await (await self.conn.execute("pragma synchronous=NORMAL")).close()
        await self.create_tables()
        self._pool = DBReadConnPool(self.path, READ_POOL_SIZE)
        await self._pool.init()
        return self

    async def __aexit__(self, *_) -> None:
        assert self._pool
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._pool.aclose())
                tg.create_task(self.conn.close())
        finally:
            self._pool = None
