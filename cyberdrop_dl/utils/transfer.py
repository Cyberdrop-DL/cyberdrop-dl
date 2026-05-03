from __future__ import annotations

import logging
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from cyberdrop_dl.database.tables.schema import CURRENT_APP_SCHEMA_VERSION, Version

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


def _get_table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def _get_column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def _get_index_names(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA index_list({table})").fetchall()
    return {r[1] for r in rows}


def _get_applied_versions(conn: sqlite3.Connection) -> list[str]:
    try:
        rows = conn.execute("SELECT version FROM schema_version").fetchall()
        return [r[0] for r in rows]
    except sqlite3.OperationalError:
        return []


def detect_version(conn: sqlite3.Connection) -> Version | None:
    tables = _get_table_names(conn)

    # v8.0.0+ introduced the schema_version
    if "schema_version" in tables:
        versions = _get_applied_versions(conn)
        if versions:
            latest = sorted(versions)[-1]
            return Version.parse(latest)

        if tables == {"media", "downloads_temp", "coomeno"}:
            return Version(4, 2, 231)

        if tables == {"media", "temp"}:
            return Version(5, 3, 31)

        if tables == {"media", "files", "hash"}:
            media_column_names = _get_column_names(conn, "media")
            if "duration" in media_column_names:
                return Version(6, 10, 1)  # v6.10.1 - v7.5.0
            return Version(6, 5, 0)

    return None


# Migration steps


def step_fix_legacy_hash_table(conn: sqlite3.Connection) -> None:
    tables = _get_table_names(conn)
    if "hash" not in tables:
        logger.debug("step_fix_legacy_hash_table: no hash table, skipping")
        return

    hash_cols = _get_column_names(conn, "hash")

    new_schema_cols = {"folder", "download_filename", "hash_type", "hash"}
    if new_schema_cols.issubset(hash_cols) and "file_size" not in hash_cols:
        logger.debug("step_fix_legacy_hash_table: already new schema")
        return

    logger.info("step_fix_legacy_hash_table: migrating legacy hash table")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS hash_new (
            folder             	TEXT NOT NULL,
            download_filename   TEXT NOT NULL,
            hash_type           TEXT NOT NULL,
            hash                TEXT NOT NULL,
            PRIMARY KEY (folder, download_filename, hash_type)
        )
    """)

    conn.execute("""
        INSERT OR IGNORE INTO hash_new (folder, download_filename, hash_type, hash)
        SELECT folder, download_filename, 'md5', hash
        FROM hash
        WHERE hash IS NOT NULL AND hash != ''
    """)

    conn.execute("DROP TABLE hash")
    conn.execute("ALTER TABLE hash_new RENAME TO hash")
    logger.info("step_fix_legacy_hash_table: done")


def step_migrate_media_to_files(conn: sqlite3.Connection) -> None:
    tables = _get_table_names(conn)
    if "media" not in tables:
        logger.debug("step_migrate_media_to_files: no media table, skipping")
        return

    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            folder              TEXT NOT NULL,
            download_filename   TEXT NOT NULL,
            original_filename   TEXT,
            file_size           INT,
            referer             TEXT,
            date                INT,
            PRIMARY KEY (folder, download_filename)
        )
    """)

    existing_count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    media_count = conn.execute("SELECT COUNT(*) FROM media WHERE download_path IS NOT NULL").fetchone()[0]

    if existing_count >= media_count and existing_count > 0:
        logger.debug("step_migrate_media_to_files: files table already populated")
        return

    media_cols = _get_column_names(conn, "media")
    has_file_size = "file_size" in media_cols

    logger.info("step_migrate_media_to_files: migrating %d media rows → files", media_count)

    rows = conn.execute(
        """
        SELECT download_path, download_filename, original_filename,
            referer, created_at
            {file_size_col}
        FROM   media
        WHERE  download_path IS NOT NULL
    """.format(file_size_col=", file_size" if has_file_size else ", NULL AS file_size")
    ).fetchall()

    to_insert = []
    for dl_path, dl_fname, orig_fname, referer, created_at, file_size in rows:
        folder = str(Path(dl_path).parent) if dl_path else None

        date_epoch: int | None = None
        if created_at:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(str(created_at), fmt)
                    date_epoch = int(dt.replace(tzinfo=UTC).timestamp())
                    break
                except ValueError:
                    continue

        to_insert.append((folder, dl_fname, orig_fname, file_size, referer, date_epoch))

    conn.executemany(
        """
        INSERT OR IGNORE INTO files
            (folder, download_filename, original_filename, file_size, referer, date)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        to_insert,
    )
    logger.info("step_migrate_media_to_files: inserted %d rows", len(to_insert))


def step_add_missing_media_columns(conn: sqlite3.Connection) -> None:
    tables = _get_table_names(conn)
    if "media" not in tables:
        logger.debug("step_add_missing_media_columns: no media table, skipping")
        return

    cols = _get_column_names(conn, "media")

    if "file_size" not in cols:
        logger.info("step_add_missing_media_columns: adding file_size")
        conn.execute("ALTER TABLE media ADD COLUMN file_size INT")

    if "duration" not in cols:
        logger.info("step_add_missing_media_columns: adding duration")
        conn.execute("ALTER TABLE media ADD COLUMN duration FLOAT")


def step_create_schema_version(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version     VARCHAR(50) PRIMARY KEY,
            applied_on  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    already = conn.execute(
        "SELECT 1 FROM schema_version WHERE version = ?", (str(CURRENT_APP_SCHEMA_VERSION),)
    ).fetchone()

    if already:
        logger.debug("step_create_schema_version: %s already recorded", CURRENT_APP_SCHEMA_VERSION)
        return

    conn.execute("INSERT INTO schema_version(version) VALUES (?)", (str(CURRENT_APP_SCHEMA_VERSION),))
    logger.info("step_create_schema_version: recorded version %s", CURRENT_APP_SCHEMA_VERSION)


# Ordered list of migration steps
MIGRATION_STEPS: list[Callable[[sqlite3.Connection], None]] = [
    step_fix_legacy_hash_table,
    step_migrate_media_to_files,
    step_add_missing_media_columns,
    step_create_schema_version,
]


class TransferManager:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def run(self, *, force: bool = False) -> None:
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=OFF")

        try:
            version = detect_version(conn)
            logger.info("Detected schema version: %s", version)

            if not force and version == CURRENT_APP_SCHEMA_VERSION:
                logger.info(
                    "Database is already at the latest schema (%s). Use --force to re-run migrations.",
                    CURRENT_APP_SCHEMA_VERSION,
                )
                return

            backup_path = self._backup()
            logger.info("Backup written to: %s", backup_path)

            self._run_steps(conn)

            conn.commit()
            logger.info("Migration completed successfully → version %s", CURRENT_APP_SCHEMA_VERSION)

        except Exception:
            conn.rollback()
            logger.exception("Migration failed — database has NOT been modified")
            raise
        finally:
            conn.close()

    def _backup(self) -> Path:
        stem = self.db_path.stem
        suffix = self.db_path.suffix
        backup_path = self.db_path.with_name(f"{stem}.backup{suffix}")
        shutil.copy2(self.db_path, backup_path)
        return backup_path

    def _run_steps(self, conn: sqlite3.Connection) -> None:
        for step in MIGRATION_STEPS:
            logger.info("Running migration step: %s", step.__name__)
            step(conn)
            logger.info("  ✓ %s", step.__name__)
