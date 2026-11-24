from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Self

from cyberdrop_dl import aio
from cyberdrop_dl.database.hash import HashTable
from cyberdrop_dl.database.history import HistoryTable
from cyberdrop_dl.database.pool import PoolManager
from cyberdrop_dl.database.schema import SchemaTable
from cyberdrop_dl.signature import dataclass_repr

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from cyberdrop_dl.database.conn import DBConnection


@dataclass_repr("path", "ignore_history")
class Database:
    def __init__(
        self,
        path: Path,
        ignore_history: bool = False,  # noqa: FBT001, FBT002
        *,
        _auto_transfer: bool = True,
    ) -> None:
        self.path: Path = path
        self._in_use: bool = False
        self._pool_mgr: PoolManager = PoolManager(path)
        self._auto_transfer: bool = _auto_transfer
        self.ignore_history: bool = ignore_history
        self.history: HistoryTable = HistoryTable(self._pool_mgr, ignore_history)
        self.hash: HashTable = HashTable(self._pool_mgr, ignore_history)
        self.schema: SchemaTable = SchemaTable(self._pool_mgr, ignore_history)
        self.is_new: bool

    @property
    def conn(self) -> DBConnection:
        return self._pool_mgr.get_writer()

    async def _create_tables(self) -> None:
        await self.schema.create()
        if not self.is_new:
            self.schema.check_version()
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

    async def _transfer(self) -> None:
        if self.is_new or not self._auto_transfer:
            return

        from .transfer import run

        await asyncio.to_thread(run, self.path, cli=False)

    @classmethod
    @contextlib.asynccontextmanager
    async def connect_w_no_pool(cls, path: Path) -> AsyncGenerator[Self]:
        "Connect to db with a single connection for simple operations"
        self = cls(path)
        self.is_new = not await aio.get_size(self.path)
        await self._pool_mgr.connect_writer()
        try:
            self._in_use = True
            yield self
        finally:
            await self.conn.close()
            self._in_use = False

    async def __aenter__(self) -> Self:
        if self._in_use:
            raise RuntimeError("Database context was already entered by another task")

        self._in_use = True
        self.is_new = not await aio.get_size(self.path)
        await self._transfer()
        await self._pool_mgr.connect_writer()
        await self.create_tables()
        await self._pool_mgr.init_pool()
        return self

    async def __aexit__(self, *_) -> None:
        assert self._in_use
        await self._pool_mgr.aclose()
        self._in_use = False
