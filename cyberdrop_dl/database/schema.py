from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING, NamedTuple, final

import aiosqlite

from cyberdrop_dl.exceptions import DatabaseError

from .common import Table
from .definitions import CREATE_SCHEMA

if TYPE_CHECKING:
    import aiosqlite


@final
class Version(NamedTuple):
    major: int
    minor: int = 0
    patch: int = 0

    @staticmethod
    def parse(string: str) -> Version:
        parts = string.split(".")
        if not parts or len(parts) > 3:
            raise ValueError(f"Invalid version string {string}")
        return Version(*map(int, parts))

    def __str__(self) -> str:
        return ".".join(map(str, self))


CURRENT_VERSION = Version(10, 1, 0)
REQUIRED_VERSION = Version(9, 15, 0)

logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class SchemaTable(Table, name="schema_version"):
    up_to_date: bool = False
    version: Version | None = None

    async def get_version(self) -> Version | None:
        if not await self.exists():
            return None
        query = "SELECT version FROM schema_version ORDER BY ROWID DESC LIMIT 1;"
        cursor = await self.db_conn.execute(query)
        if row := await cursor.fetchone():
            return Version.parse(row["version"])

    async def create(self) -> None:
        logger.info(f"Expected database schema: {CURRENT_VERSION!s}")
        self.version = await self.get_version()
        logger.info(f"Current database schema: {self.version!s}")
        await self.db_conn.execute(CREATE_SCHEMA)
        await self.db_conn.commit()

    def check_version(self) -> None:
        error = None
        if self.version is None:
            error = DatabaseError(f"Database has no schema information. Minimum required version: {REQUIRED_VERSION}")
        elif self.version < REQUIRED_VERSION:
            error = DatabaseError(
                f"Incompatible database version detected. Current: {self.version!s} - Required: {REQUIRED_VERSION!s}"
            )
        elif self.version >= CURRENT_VERSION:
            self.up_to_date = True

        if error:
            error.add_note("Run 'cyberdrop-dl database transfer' to upgrade the database to a new version")
            raise error

    async def update(self, version: Version = CURRENT_VERSION) -> None:
        query = "INSERT INTO schema_version (version) VALUES (?)"
        _ = await self.db_conn.execute(query, (str(version),))
        await self.db_conn.commit()
        self.version = version
        self.up_to_date = version >= CURRENT_VERSION
        logger.info(f"Updated database schema to {version!s}")


async def dump(db_conn: aiosqlite.Connection) -> str:
    query = "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY name"
    rows = await db_conn.execute_fetchall(query)
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
