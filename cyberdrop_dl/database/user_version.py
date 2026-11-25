"Flags to check migrations applied to the database"

from __future__ import annotations

import contextlib
import enum
from typing import TYPE_CHECKING

from cyberdrop_dl import aio

if TYPE_CHECKING:
    import sqlite3

    import aiosqlite


class Marker(enum.IntFlag):
    BRAND_NEW = 0
    DOMAINS_FIXED = 1
    FILES_TRANSFER_COMPLETED = 2


UP_TO_DATE = Marker.BRAND_NEW | Marker.DOMAINS_FIXED | Marker.FILES_TRANSFER_COMPLETED


def get(conn: sqlite3.Connection) -> Marker:
    with contextlib.closing(conn.execute("PRAGMA user_version;")) as cursor:
        return Marker(cursor.fetchone()[0])


def update(conn: sqlite3.Connection, new_version: Marker) -> None:
    value = int(Marker(new_version))
    conn.execute(f"PRAGMA user_version = {value} ;").close()


async def aget(conn: aiosqlite.Connection) -> Marker:
    async with aio.closing(await conn.execute("PRAGMA user_version;")) as cursor:
        row = await cursor.fetchone()
        assert row is not None
        return Marker(row[0])


async def aupdate(conn: aiosqlite.Connection, new_version: Marker) -> None:
    value = int(Marker(new_version))
    await (await conn.execute(f"PRAGMA user_version = {value} ;")).close()
