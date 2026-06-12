from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING, NamedTuple

import aiosqlite

from cyberdrop_dl.exceptions import DatabaseError

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


CURRENT_APP_SCHEMA_VERSION = Version(10, 0, 0)
REQUIRED_APP_SCHEMA_VERSION = Version(9, 15, 0)

logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class SchemaVersionTable:
    _database: Database
    _up_to_date: bool = False
    _version: Version | None = None

    @property
    def up_to_date(self) -> bool:
        return self._up_to_date

    @property
    def db_conn(self) -> aiosqlite.Connection:
        return self._database._db_conn

    async def _get_version(self) -> Version | None:
        if not await self._database.exists("schema_version"):
            return None
        query = "SELECT version FROM schema_version ORDER BY ROWID DESC LIMIT 1;"
        cursor = await self.db_conn.execute(query)
        if row := await cursor.fetchone():
            return Version.parse(row["version"])

    async def __update_schema_version(self, version: Version) -> None:
        query = "INSERT INTO schema_version (version) VALUES (?)"
        _ = await self.db_conn.execute(query, (str(version),))
        await self.db_conn.commit()
        self._version = version

    async def create(self) -> None:
        logger.info(f"Expected database schema: {CURRENT_APP_SCHEMA_VERSION!s}")
        self._version = await self._get_version()
        logger.info(f"Current database schema: {self._version!s}")
        await self.db_conn.execute(create_schema_version)
        await self.db_conn.commit()

    def check_version(self) -> None:
        if self._version is None:
            raise DatabaseError(
                f"Database has not schema information. Min required version: {REQUIRED_APP_SCHEMA_VERSION}"
            )
        if self._version < REQUIRED_APP_SCHEMA_VERSION:
            raise DatabaseError(
                f"Incompatible database version detected. Current: {self._version!s} , Minimum required: {REQUIRED_APP_SCHEMA_VERSION!s}"
            )
        if self._version >= CURRENT_APP_SCHEMA_VERSION:
            self._up_to_date = True

    async def update(self, version: Version = CURRENT_APP_SCHEMA_VERSION) -> None:
        await self.__update_schema_version(version)
        logger.info(f"Updated database schema to {version!s}")
        self._up_to_date = version >= CURRENT_APP_SCHEMA_VERSION
