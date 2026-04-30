from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING, NamedTuple

import aiosqlite

from .definitions import create_schema_version

if TYPE_CHECKING:
    import aiosqlite

    from cyberdrop_dl.database import Database


class Version(NamedTuple):
    major: int
    minor: int
    patch: int

    @staticmethod
    def parse(string: str) -> Version:
        return Version(*map(int, string.split(".")[:3]))

    def __str__(self) -> str:
        return ".".join(map(str, self))


CURRENT_APP_SCHEMA_VERSION = Version(9, 4, 2)

logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True, frozen=True)
class SchemaVersionTable:
    _database: Database

    @property
    def db_conn(self) -> aiosqlite.Connection:
        return self._database._db_conn

    async def get_version(self) -> Version | None:
        if not await self.__exists():
            return
        query = "SELECT version FROM schema_version ORDER BY ROWID DESC LIMIT 1;"
        cursor = await self.db_conn.execute(query)
        result = await cursor.fetchone()
        if result:
            return Version.parse(result["version"])

    async def __exists(self) -> bool:
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version';"
        cursor = await self.db_conn.execute(query)
        result = await cursor.fetchone()
        return result is not None

    async def __create_if_not_exists(self) -> None:
        await self.db_conn.execute(create_schema_version)
        await self.db_conn.commit()

    async def __update_schema_version(self) -> None:
        await self.__create_if_not_exists()
        query = "INSERT INTO schema_version (version) VALUES (?)"
        _ = await self.db_conn.execute(query, (str(CURRENT_APP_SCHEMA_VERSION),))
        await self.db_conn.commit()

    async def create(self) -> None:
        logger.info(f"Expected database schema version: {CURRENT_APP_SCHEMA_VERSION!s}")
        version = await self.get_version()
        logger.info(f"Database reports installed version: {version!s}")
        if version is not None and version >= CURRENT_APP_SCHEMA_VERSION:
            return

        # TODO: on v9, raise SystemExit if db version is None or older than 8.0.0
        logger.info(f"Updating database version to {CURRENT_APP_SCHEMA_VERSION!s}")
        await self.__update_schema_version()
