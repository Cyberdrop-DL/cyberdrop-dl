from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from cyberdrop_dl import aio
from cyberdrop_dl.database import user_version
from cyberdrop_dl.database.backup import (
    backup_database,
    create_db_path_w_timestamp,
    delete_database,
    merge_journal_files,
)
from cyberdrop_dl.database.common import get_column_names, get_table_names
from cyberdrop_dl.database.conn import connect, stdlib_connect
from cyberdrop_dl.database.db import Database
from cyberdrop_dl.database.history import apply_fixes
from cyberdrop_dl.database.schema import CURRENT_VERSION, Version, get_schema
from cyberdrop_dl.logs import setup_console_logging
from cyberdrop_dl.utils import dates

if TYPE_CHECKING:
    import sqlite3

logger = logging.getLogger(__name__)


def _get_column_info(conn: sqlite3.Connection, table: str, schema: str = "main") -> list[tuple[str, str | None]]:
    """Return `[(col_name, default_value), ...]` for every column in *table*.

    *default_value* is the literal SQL default from the schema, or `None` when no default is declared."""

    # PRAGMA table_info columns: cid | name | type | notnull | dflt_value | pk
    with contextlib.closing(conn.execute(f"PRAGMA {schema}.table_info({table})")) as cursor:
        return [(r[1], r[4]) for r in cursor.fetchall()]


def _transfer_table(new_conn: sqlite3.Connection, table: str) -> None:
    """Transfer rows from `old.<table>` into the new `<table>`.

    The SELECT list is built dynamically:
    - columns that exist in the old table are selected by name;
    - columns that are only in the current schema are filled with their declared schema default or `NULL`."""

    old_tables = get_table_names(new_conn, schema="old")
    if table not in old_tables:
        logger.debug("_transfer_table: %s absent in old DB, skipping", table)
        return

    old_cols = get_column_names(new_conn, table, schema="old")
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
    new_conn.execute(f'INSERT OR IGNORE INTO "{table}" ({cols_sql}) SELECT {select_sql} FROM old."{table}"').close()  # noqa: S608


def _transfer_media_to_files(new_conn: sqlite3.Connection) -> None:
    """Populate the new `files` table from `old.media`."""

    old_tables = get_table_names(new_conn, schema="old")
    if "media" not in old_tables:
        logger.debug("_transfer_media_to_files: no old media table, skipping")
        return

    old_media_cols = get_column_names(new_conn, "media", schema="old")
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
        """  # noqa: S608
    )


# TransferManager

# Tables whose rows are transferred column-by-column, in dependency order.
_DIRECT_TRANSFER_TABLES = ["media", "hash", "files", "schema_version"]

_SKIP_TABLES = set()


def _needs_update(db_path: Path) -> bool:
    with contextlib.closing(stdlib_connect(db_path, "files transfer check")) as probe:
        return user_version.Marker.FILES_TRANSFER_COMPLETED not in user_version.get(probe)


def run(db_path: Path, *, force: bool = False) -> bool:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    schema = get_schema(db_path)
    schema.log()
    if force or _needs_update(db_path):
        _run(db_path, schema.version)
        return True
    return False


def live_transfer(db_path: Path, version: Version | None) -> bool:
    if _needs_update(db_path):
        _run(db_path, version)
        return True
    return False


def _run(db_path: Path, old_version: Version | None) -> None:
    now = dates.now()
    db_backup_path = create_db_path_w_timestamp(db_path, old_version, now).with_suffix(f".backup{db_path.suffix}")
    new_temp_db = create_db_path_w_timestamp(db_path, CURRENT_VERSION, now)

    logger.debug("Creating new database at: %s", new_temp_db)
    _create_new_database(new_temp_db)
    backup_database(db_path, db_backup_path)

    with contextlib.closing(stdlib_connect(new_temp_db, "new database")) as new_conn:
        cursor = new_conn.execute("PRAGMA busy_timeout = 100;")
        cursor.execute("PRAGMA main.locking_mode = EXCLUSIVE;")
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute("ATTACH DATABASE ? AS old", (str(db_path),))
        cursor.execute("PRAGMA old.locking_mode = EXCLUSIVE;").close()
        try:
            _transfer(new_conn)
        except Exception:
            new_conn.rollback()
            new_conn.close()
            logger.exception("Transfer failed - original database has NOT been changed")
            new_temp_db.unlink()
            raise
        else:
            new_conn.commit()

    _apply_fixes(new_temp_db)
    delete_database(db_path)
    merge_journal_files(new_temp_db)
    new_temp_db.rename(db_path)
    logger.info("Transfer complete!", extra={"color": "green"})
    logger.info("New schema version: %s", CURRENT_VERSION)


def _create_new_database(path: Path) -> None:
    async def connect() -> None:
        async with Database(path, ignore_history=True, _auto_transfer=False):
            pass

    asyncio.run(connect())


def _apply_fixes(db_path: Path) -> None:

    async def fix() -> None:
        async with aio.closing(await connect(db_path)) as conn:
            await apply_fixes(conn)

    asyncio.run(fix())


def _transfer(new_conn: sqlite3.Connection) -> None:
    old_tables = get_table_names(new_conn, schema="old")
    new_tables = get_table_names(new_conn, schema="main")

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

    new_user_version = user_version.get(new_conn) | user_version.Marker.FILES_TRANSFER_COMPLETED
    user_version.update(new_conn, new_user_version)


if __name__ == "__main__":
    with setup_console_logging():
        run(Path(sys.argv[1]))
