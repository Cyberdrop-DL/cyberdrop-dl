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
    from types import TracebackType

    import aiosqlite


READ_POOL_SIZE = 4


def _current_task() -> asyncio.Task[Any]:
    task = asyncio.current_task()
    assert task is not None
    return task


def _drain_queue(queue: asyncio.Queue[Any]) -> None:
    while True:
        try:
            _ = queue.get_nowait()
        except asyncio.QueueEmpty:
            break


class Database:
    def __init__(self, path: Path, ignore_history: bool = False) -> None:  # noqa: FBT001, FBT002
        self.path: Path = path
        self.ignore_history: bool = ignore_history

        self._readers: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue(READ_POOL_SIZE)
        self._writer_task: asyncio.Task[Any] | None = None
        self._busy: dict[asyncio.Task[Any], aiosqlite.Connection] = {}
        self._write_lock: asyncio.Lock = asyncio.Lock()
        self._stack: contextlib.AsyncExitStack = contextlib.AsyncExitStack()

        self.history: HistoryTable = HistoryTable(self)
        self.hash: HashTable = HashTable(self)
        self.schema: SchemaTable = SchemaTable(self)
        self._pool_ready: bool = False

        self.conn: aiosqlite.Connection
        self.is_new: bool

    __repr__ = simple_repr("path", "ignore_history")

    async def _connect(self) -> None:
        self.is_new = not await aio.get_size(self.path)
        self.conn = await raw_connect(self.path, "db-writer")

    async def _init_pool(self) -> None:
        assert not self._pool_ready

        async def new_conn(idx: int) -> None:
            conn = await self._stack.enter_async_context(connect(self.path, name=f"db-reader-{idx}"))
            await conn.execute("pragma query_only")
            self._readers.put_nowait(conn)

        async with asyncio.TaskGroup() as tg:
            for idx in range(READ_POOL_SIZE):
                tg.create_task(new_conn(idx))

        self._stack.callback(_drain_queue, self._readers)
        self._pool_ready = True

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
        async with self._reader() as conn:
            if conn.in_transaction:
                yield conn
                return

            await conn.execute("BEGIN DEFERRED;")
            try:
                yield conn
            finally:
                # discard accidental commits if conn is the writter conn
                await conn.rollback()

    @contextlib.asynccontextmanager
    async def _reader(self) -> AsyncGenerator[aiosqlite.Connection]:
        if not self._pool_ready:
            yield self.conn
            return

        task = _current_task()
        if self._writer_task == task:
            yield self.conn
            return

        if (conn := self._busy.get(task)) is not None:
            yield conn
            return

        conn = self._busy[task] = await self._readers.get()
        try:
            yield conn
        finally:
            del self._busy[task]
            self._readers.put_nowait(conn)

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
        await self._stack.__aenter__()
        await self._init_pool()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._pool_ready = False

        await self._stack.__aexit__(exc_type, exc_value, traceback)
        await self.conn.close()
        exc_type = exc_value = traceback = None
