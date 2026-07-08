from __future__ import annotations

import contextlib
import dataclasses
from typing import TYPE_CHECKING, Self

from cyberdrop_dl import aio

from .common import pre_allocate_250mb, raw_connect
from .hash import HashTable
from .history import HistoryTable
from .schema import SchemaTable

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    import aiosqlite


@dataclasses.dataclass(slots=True)
class Database:
    path: Path
    ignore_history: bool = False

    history: HistoryTable = dataclasses.field(init=False)
    hash: HashTable = dataclasses.field(init=False)
    schema: SchemaTable = dataclasses.field(init=False)

    conn: aiosqlite.Connection = dataclasses.field(init=False)
    is_new: bool = dataclasses.field(init=False)

    async def _connect(self) -> None:
        self.is_new = not await aio.get_size(self.path)
        self.conn = await raw_connect(self.path)
        self.history = HistoryTable(self.conn, self.ignore_history)
        self.hash = HashTable(self.conn, self.ignore_history)
        self.schema = SchemaTable(self.conn, self.ignore_history)

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
        await self.create_tables()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.conn.close()
