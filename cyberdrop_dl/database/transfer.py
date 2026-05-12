from __future__ import annotations

import asyncio
import datetime
import logging
import sqlite3
import sys
from pathlib import Path

from cyberdrop_dl.database import Database, connect
from cyberdrop_dl.database.tables.history import fix_domains, fix_referers
from cyberdrop_dl.database.tables.schema import CURRENT_APP_SCHEMA_VERSION, Version
from cyberdrop_dl.logs import setup_console_logging
from cyberdrop_dl.utils.filepath import sanitize_filename

logger = logging.getLogger(__name__)


def _get_table_names(conn: sqlite3.Connection, schema: str = "main") -> set[str]:
    rows = conn.execute(f"SELECT name FROM {schema}.sqlite_master WHERE type='table'").fetchall()
    return {r[0] for r in rows}


def _get_column_names(conn: sqlite3.Connection, table: str, schema: str = "main") -> set[str]:
    rows = conn.execute(f"PRAGMA {schema}.table_info({table})").fetchall()
    return {r[1] for r in rows}


def _get_column_info(conn: sqlite3.Connection, table: str, schema: str = "main") -> list[tuple[str, str | None]]:
    """Return `[(col_name, default_value), ...]` for every column in *table*.

    *default_value* is the literal SQL default from the schema, or `None` when no default is declared."""

    # PRAGMA table_info columns: cid | name | type | notnull | dflt_value | pk
    rows = conn.execute(f"PRAGMA {schema}.table_info({table})").fetchall()
    return [(r[1], r[4]) for r in rows]


def _get_applied_versions(conn: sqlite3.Connection) -> list[str]:
    try:
        rows = conn.execute("SELECT version FROM schema_version").fetchall()
        return [r[0] for r in rows]
    except sqlite3.OperationalError:
        return []


def detect_version(conn: sqlite3.Connection) -> Version | None:
    tables = _get_table_names(conn)

    if "schema_version" in tables:
        versions = _get_applied_versions(conn)
        if versions:
            return Version.parse(sorted(versions)[-1])

    if tables == {"media", "downloads_temp", "coomeno"}:
        return Version(4, 2, 231)

    if tables == {"media", "temp"}:
        return Version(5, 3, 31)

    if tables == {"media", "files", "hash"}:
        media_cols = _get_column_names(conn, "media")
        if "duration" in media_cols:
            return Version(6, 10, 1)  # v6.10.1 - v7.5.0
        return Version(6, 5, 0)

    return None


def _transfer_table(new_conn: sqlite3.Connection, table: str) -> None:
    """Transfer rows from `old.<table>` into the new `<table>`.

    The SELECT list is built dynamically:
    - columns that exist in the old table are selected by name;
    - columns that are only in the current schema are filled with their declared schema default or `NULL`."""

    old_tables = _get_table_names(new_conn, schema="old")
    if table not in old_tables:
        logger.debug("_transfer_table: %s absent in old DB, skipping", table)
        return

    old_cols = _get_column_names(new_conn, table, schema="old")
    new_col_info = _get_column_info(new_conn, table, schema="main")

    col_names: list[str] = []
    select_exprs: list[str] = []

    for name, default in new_col_info:
        col_names.append(f'"{name}"')
        if name in old_cols:
            select_exprs.append(f'"{name}"')
        else:
            # Use the declared default value, or NULL when none is specified.
            fallback = default if default is not None else "NULL"
            select_exprs.append(f'{fallback} AS "{name}"')

    cols_sql = ", ".join(col_names)
    select_sql = ", ".join(select_exprs)

    logger.info("_transfer_table: old.%s -> %s", table, table)
    new_conn.execute(f'INSERT OR IGNORE INTO "{table}" ({cols_sql}) SELECT {select_sql} FROM old."{table}"')


def _transfer_media_to_files(new_conn: sqlite3.Connection) -> None:
    """Populate the new `files` table from `old.media`."""

    old_tables = _get_table_names(new_conn, schema="old")
    if "media" not in old_tables:
        logger.debug("_transfer_media_to_files: no old media table, skipping")
        return

    old_media_cols = _get_column_names(new_conn, "media", schema="old")
    file_size_expr = '"file_size"' if "file_size" in old_media_cols else "NULL"

    logger.info("_transfer_media_to_files: old.media -> files")
    # download_path is not absolute in older versions, but we can still use it to populate the folder column.
    new_conn.execute(
        f"""
        INSERT OR IGNORE INTO "files"
            ("folder", "download_filename", "original_filename", "file_size", "referer", "date")
        SELECT
            "download_path",
            "download_filename",
            "original_filename",
            {file_size_expr},
            "referer",
            CAST(strftime('%s', "created_at") AS INTEGER)
        FROM old."media"
        WHERE "download_path" IS NOT NULL
        """
    )


# TransferManager

# Tables whose rows are transferred column-by-column, in dependency order.
_DIRECT_TRANSFER_TABLES = ["media", "hash", "files"]

_SKIP_TABLES = {"schema_version"}


def run(db_path: Path, *, force: bool = False) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    with sqlite3.connect(db_path) as probe:
        old_version = detect_version(probe)

    logger.info("Detected schema version: %s", old_version)

    if not force and old_version == CURRENT_APP_SCHEMA_VERSION:
        logger.info(
            "Database is already at the latest schema (%s). Use --force to re-run.",
            CURRENT_APP_SCHEMA_VERSION,
        )
        return

    now = sanitize_filename(str(datetime.datetime.now()))
    new_path = db_path.with_name(f"{db_path.stem}_{CURRENT_APP_SCHEMA_VERSION}_{now}{db_path.suffix}")

    logger.debug("Creating new database at: %s", new_path)
    _create_new_database(new_path)
    with sqlite3.connect(new_path) as new_conn:
        new_conn.execute("PRAGMA foreign_keys=OFF")
        new_conn.execute(f"ATTACH DATABASE '{db_path}' AS old")
        try:
            _transfer(new_conn)
        except Exception:
            new_conn.rollback()
            new_conn.close()
            logger.exception("Transfer failed - original database has NOT been changed")
            new_path.unlink()
            raise
        else:
            new_conn.commit()

    _apply_fixes(new_path)
    backup_path = db_path.with_name(f"{db_path.stem}_{old_version}_{now}.backup{db_path.suffix}")
    db_path.rename(backup_path)
    new_path.rename(db_path)
    logger.info("Transfer complete", extra={"color": "green"})
    logger.info("Backup at: '%s'", backup_path)
    logger.info("New schema version: %s", CURRENT_APP_SCHEMA_VERSION)


def _create_new_database(path: Path) -> None:
    async def connect() -> None:
        async with Database(_db_path=path, ignore_history=True):
            pass

    asyncio.run(connect())


def _apply_fixes(db_path: Path) -> None:

    async def fix() -> None:
        conn = await connect(db_path)
        try:
            await fix_domains(conn)
            await fix_referers(conn)
        finally:
            await conn.close()

    asyncio.run(fix())


def _transfer(new_conn: sqlite3.Connection) -> None:
    old_tables = _get_table_names(new_conn, schema="old")
    new_tables = _get_table_names(new_conn, schema="main")

    for table in _DIRECT_TRANSFER_TABLES:
        if table not in new_tables or table in _SKIP_TABLES:
            continue

        if table == "files" and "files" not in old_tables:
            _transfer_media_to_files(new_conn)
        else:
            _transfer_table(new_conn, table)

    # Transfer any remaining new tables not listed
    covered = set(_DIRECT_TRANSFER_TABLES) | _SKIP_TABLES
    for table in sorted(new_tables - covered):
        _transfer_table(new_conn, table)


if __name__ == "__main__":
    with setup_console_logging():
        run(Path(sys.argv[1]))
