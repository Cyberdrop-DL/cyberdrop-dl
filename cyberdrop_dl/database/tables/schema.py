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
        return self._database.conn

    async def _get_version(self) -> Version | None:
        if not await self._database.exists("schema_version"):
            return None
        query = "SELECT version FROM schema_version ORDER BY ROWID DESC LIMIT 1;"
        cursor = await self.db_conn.execute(query)
        if row := await cursor.fetchone():
            return Version.parse(row["version"])

    async def create(self) -> None:
        logger.info(f"Expected database schema: {CURRENT_APP_SCHEMA_VERSION!s}")
        self._version = await self._get_version()
        logger.info(f"Current database schema: {self._version!s}")
        await self.db_conn.execute(create_schema_version)
        await self.db_conn.commit()

    def check_version(self) -> None:
        if self._version is None:
            raise DatabaseError(
                f"Database has no schema information. Minimum required version: {REQUIRED_APP_SCHEMA_VERSION}"
            )
        if self._version < REQUIRED_APP_SCHEMA_VERSION:
            raise DatabaseError(
                f"Incompatible database version detected. Current: {self._version!s} , Minimum required: {REQUIRED_APP_SCHEMA_VERSION!s}"
            )
        if self._version >= CURRENT_APP_SCHEMA_VERSION:
            self._up_to_date = True

    async def update(self, version: Version = CURRENT_APP_SCHEMA_VERSION) -> None:
        query = "INSERT INTO schema_version (version) VALUES (?)"
        _ = await self.db_conn.execute(query, (str(version),))
        await self.db_conn.commit()
        self._version = version
        self._up_to_date = version >= CURRENT_APP_SCHEMA_VERSION
        logger.info(f"Updated database schema to {version!s}")


async def dump(db_conn: aiosqlite.Connection) -> str:
    query = "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"
    cursor = await db_conn.execute(query)
    rows = await cursor.fetchall()
    index_queries: list[str] = []
    table_queries: list[str] = []

    for query in (row["sql"] for row in rows):
        group = table_queries if "CREATE TABLE" in query else index_queries
        group.append(query)

    return ";\n".join([*sorted(table_queries), *sorted(index_queries)]) + ";"


V9_15_0 = """
CREATE TABLE files (
  folder TEXT,
  download_filename TEXT,
  original_filename TEXT,
  file_size INT,
  referer TEXT,
  date INT,
  PRIMARY KEY (folder, download_filename)
);
CREATE TABLE hash (
  folder TEXT,
  download_filename TEXT,
  hash_type TEXT,
  hash TEXT,
  PRIMARY KEY (folder, download_filename, hash_type),
  FOREIGN KEY (folder, download_filename) REFERENCES files(folder, download_filename)
);
CREATE TABLE media (
  domain TEXT,
  url_path TEXT,
  referer TEXT,
  download_path TEXT,
  download_filename TEXT,
  original_filename TEXT,
  file_size INT,
  duration FLOAT,
  album_id TEXT,
  completed INTEGER NOT NULL,
  created_at TIMESTAMP,
  completed_at TIMESTAMP,
  PRIMARY KEY (domain, url_path, original_filename)
);
CREATE TABLE schema_version (
    version VARCHAR(50) NOT NULL PRIMARY KEY,
    applied_on TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_hash_type_hash ON hash (hash_type, hash);
CREATE INDEX idx_media_domain_album
    ON media (domain, album_id);
CREATE INDEX idx_media_domain_referer_completed
    ON media (domain, referer, completed);
CREATE INDEX idx_media_domain_url_path_referer
    ON media (domain, url_path, referer);
CREATE INDEX idx_media_referer_completed
    ON media (referer, completed);
""".strip()
