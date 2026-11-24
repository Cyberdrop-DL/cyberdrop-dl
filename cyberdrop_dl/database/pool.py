from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

from cyberdrop_dl import aio
from cyberdrop_dl.database.conn import connect
from cyberdrop_dl.signature import dataclass_repr

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from cyberdrop_dl.database.conn import DBConnection


READ_POOL_SIZE = 10


@dataclass_repr("_queue", "_busy", "_stack")
class DBReadConnPool:
    def __init__(self, path: Path, size: int) -> None:
        self.path: Path = path
        self._queue: asyncio.Queue[DBConnection] = asyncio.Queue(size)
        self._busy: dict[asyncio.Task[Any], DBConnection] = {}
        self._stack: contextlib.AsyncExitStack = contextlib.AsyncExitStack()

    async def _new_conn(self, idx: int) -> None:
        conn = await self._stack.enter_async_context(aio.closing(await connect(self.path, name=f"db-reader-{idx}")))
        await conn.execute_and_close("PRAGMA query_only=ON")
        self._queue.put_nowait(conn)

    async def init(self) -> None:
        await self._stack.__aenter__()
        async with asyncio.TaskGroup() as tg:
            for idx in range(self._queue.maxsize):
                tg.create_task(self._new_conn(idx))

    async def aclose(self) -> None:
        await self._stack.__aexit__(None, None, None)
        while True:
            try:
                _ = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    @contextlib.asynccontextmanager
    async def __call__(self) -> AsyncGenerator[DBConnection]:
        task = aio.current_task()
        if (conn := self._busy.get(task)) is not None:
            yield conn
            return

        conn = self._busy[task] = await self._queue.get()
        try:
            yield conn
        finally:
            del self._busy[task]
            self._queue.put_nowait(conn)


@dataclass_repr("path", "_pool")
class PoolManager:
    def __init__(self, path: Path) -> None:
        self.path: Path = path
        self._pool: DBReadConnPool | None = None
        self._writer_task: asyncio.Task[Any] | None = None
        self._write_lock: asyncio.Lock = asyncio.Lock()
        self._writer: DBConnection | None = None

    def get_writer(self) -> DBConnection:
        if self._writer is None:
            raise RuntimeError("There is no active connection")
        return self._writer

    async def connect_writer(self) -> None:
        if self._writer is not None:
            raise RuntimeError("A writer connection is already available")

        self._writer = await connect(self.path, "db-writer")

    @contextlib.asynccontextmanager
    async def writer(self) -> AsyncGenerator[DBConnection]:
        task = aio.current_task()
        writer = self.get_writer()
        if self._writer_task == task:
            yield writer
            return

        async with self._write_lock:
            self._writer_task = task
            try:
                yield writer
            finally:
                self._writer_task = None

    @contextlib.asynccontextmanager
    async def reader(self) -> AsyncGenerator[DBConnection]:
        if self._pool is None or aio.current_task() == self._writer_task:
            yield self.get_writer()
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

    async def init_pool(self) -> None:
        await self.get_writer().execute_and_close("PRAGMA journal_mode=WAL")
        await self.get_writer().execute_and_close("PRAGMA synchronous=NORMAL")
        self._pool = DBReadConnPool(self.path, READ_POOL_SIZE)
        await self._pool.init()

    async def aclose(self) -> None:
        try:
            async with asyncio.TaskGroup() as tg:
                if self._writer is not None:
                    tg.create_task(self._writer.close())
                if self._pool is not None:
                    tg.create_task(self._pool.aclose())
        finally:
            self._pool = self._writer = None
