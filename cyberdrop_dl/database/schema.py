from __future__ import annotations

import contextlib
import dataclasses
import logging
import sqlite3
from typing import TYPE_CHECKING, NamedTuple, final, override

from cyberdrop_dl.database import user_version
from cyberdrop_dl.database.conn import stdlib_connect
from cyberdrop_dl.exceptions import DatabaseError

from .common import Table, get_column_names, get_table_names
from .definitions import CREATE_SCHEMA

if TYPE_CHECKING:
    from pathlib import Path

    from cyberdrop_dl.database.conn import DBConnection


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


CURRENT_VERSION = Version(10, 17, 1)
REQUIRED_VERSION = Version(9, 15, 0)

logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class Schema:
    version: Version | None = None
    user_ver: user_version.Marker = user_version.Marker.BRAND_NEW

    @property
    def up_to_date(self) -> bool:
        return self.version is not None and self.version >= CURRENT_VERSION and user_version.UP_TO_DATE in self.user_ver

    def log(self) -> None:
        logger.info("Current database schema:  %s", self.version)
        logger.info("Expected database schema: %s", CURRENT_VERSION)
        logger.info("Current user_version:  %s (%s)", self.user_ver, f"{self.user_ver:08b}")
        logger.info("Expected user_version: %s (%s)", user_version.UP_TO_DATE, f"{user_version.UP_TO_DATE:08b}")


def get_schema(db_path: Path) -> Schema:
    with contextlib.closing(stdlib_connect(db_path, "get schema")) as probe:
        return Schema(version=detect_version(probe), user_ver=user_version.get(probe))


@dataclasses.dataclass(slots=True)
class SchemaTable(Table, name="schema_version"):
    info: Schema = dataclasses.field(default_factory=Schema)
    log_updates: bool = False

    @override
    async def create(self) -> None:
        async with self.db.writer() as db_conn:
            await db_conn.execute_and_close(CREATE_SCHEMA)
            await db_conn.commit()

    def check_version(self) -> None:
        error = None
        if self.info.version is None:
            error = f"Database has no schema information. Minimum required version: {REQUIRED_VERSION}"

        elif self.info.version < REQUIRED_VERSION:
            error = f"Incompatible database version detected. Current: {self.info.version!s} - Required: {REQUIRED_VERSION!s}"

        if error:
            exc = DatabaseError(error)
            exc.add_note("Run 'cyberdrop-dl database transfer' to upgrade the database to a new version")
            exc.add_note(f"Full command: 'cyberdrop-dl database transfer '{self.db.path}'")
            raise exc

    async def update(self, version: Version = CURRENT_VERSION) -> None:
        if self.info.version == version:
            return

        query = "INSERT OR IGNORE INTO schema_version (version) VALUES (?)"
        async with self.db.writer() as db_conn:
            await db_conn.execute_and_close(query, (str(version),))
            await db_conn.commit()

        self.info.version = version
        if self.log_updates:
            logger.info(f"Updated database schema to {version!s}")


async def dump(db_conn: DBConnection) -> str:
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


def _get_applied_versions(conn: sqlite3.Connection) -> list[str]:
    try:
        with contextlib.closing(conn.execute("SELECT version FROM schema_version")) as cursor:
            return [r[0] for r in cursor.fetchall()]
    except sqlite3.OperationalError:
        return []


def detect_version(conn: sqlite3.Connection) -> Version | None:
    tables = get_table_names(conn)

    if "schema_version" in tables:
        versions = _get_applied_versions(conn)
        if versions:
            return max(map(Version.parse, versions))

    if tables == {"media", "downloads_temp", "coomeno"}:
        return Version(4, 2, 231)

    if tables == {"media", "temp"}:
        return Version(5, 3, 31)

    if tables == {"media", "files", "hash"}:
        media_cols = get_column_names(conn, "media")
        if "duration" in media_cols:
            return Version(6, 10, 1)  # v6.10.1 - v7.5.0
        return Version(6, 5, 0)

    return None
