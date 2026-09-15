from __future__ import annotations

import dataclasses
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, cast

from cyberdrop_dl import aio

from .common import Table
from .definitions import CREATE_FILES, CREATE_HASH, CREATE_HASH_INDEX

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    import aiosqlite

    from cyberdrop_dl.url_objects import AbsoluteHttpURL


logger = logging.getLogger(__name__)

type _FileKey = tuple[str, str]
"""A `(folder, download_filename)` pair, the primary key of both the `files` and the `hash` table"""

_CHUNK_SIZE = 400
"""Rows per query. Each row binds 2 parameters, keeping us under SQLite's 999 parameter limit"""


@dataclasses.dataclass(slots=True)
class PruneStats:
    scanned: int = 0
    missing: int = 0
    hash_rows: int = 0
    file_rows: int = 0
    dry_run: bool = False


@dataclasses.dataclass(slots=True)
class HashTable(Table, name="hash"):
    cwd: Path = dataclasses.field(init=False, default_factory=lambda: Path.cwd().expanduser().resolve())

    async def create(self) -> None:
        async with self.db.writer() as db_conn:
            for query in (CREATE_FILES, CREATE_HASH, CREATE_HASH_INDEX):
                await db_conn.execute(query)

            await db_conn.commit()

    async def get_file_hash_exists(self, path: Path | str, hash_type: str) -> str | None:
        query = "SELECT hash FROM hash WHERE folder= ? AND download_filename= ? AND hash_type= ? AND hash IS NOT NULL LIMIT 1;"
        path = self.cwd / path
        folder = str(path.parent)
        filename = path.name

        async with self.db.reader() as db_conn:
            cursor = await db_conn.execute(query, (folder, filename, hash_type))
            if row := await cursor.fetchone():
                return row["hash"]

    async def get_files_with_hash_matches(
        self,
        hash_value: str,
        size: int,
        hash_algo: str | None = None,
    ) -> list[aiosqlite.Row]:
        if hash_algo:
            query = """
            SELECT
              files.folder,
              files.download_filename,
              files.date
            FROM
              hash
              JOIN files ON hash.folder = files.folder
              AND hash.download_filename = files.download_filename
            WHERE
              hash.hash = ?
              AND files.file_size = ?
              AND hash.hash_type = ?;
            """

        else:
            query = """
            SELECT
              files.folder,
              files.download_filename
            FROM
              hash
              JOIN files ON hash.folder = files.folder
              AND hash.download_filename = files.download_filename
            WHERE
              hash.hash = ?
              AND files.file_size = ?
              AND hash.hash_type = ?;
            """

        async with self.db.reader() as db_conn:
            rows = await db_conn.execute_fetchall(query, (hash_value, size, hash_algo))

        return cast("list[aiosqlite.Row]", rows)

    async def check_hash_exists(self, hash_type: str, hash_value: str) -> bool:
        if self.ignore_history:
            return False

        query = "SELECT 1 FROM hash WHERE hash.hash_type = ? AND hash.hash = ? LIMIT 1;"
        async with self.db.reader() as db_conn:
            cursor = await db_conn.execute(query, (hash_type, hash_value))
            return await cursor.fetchone() is not None

    async def prune_missing_files(self, *, dry_run: bool = False) -> PruneStats:
        """Delete every `hash` and `files` row whose file is no longer on disk."""
        query = """
        SELECT folder, download_filename FROM files
        UNION
        SELECT folder, download_filename FROM hash;
        """
        async with self.db.reader() as db_conn:
            rows = await db_conn.execute_fetchall(query)

        known_files = [(row["folder"], row["download_filename"]) for row in rows]
        missing = await _filter_missing(known_files)
        stats = PruneStats(scanned=len(known_files), missing=len(missing), dry_run=dry_run)
        if not missing:
            return stats

        if dry_run:
            async with self.db.reader() as db_conn:
                stats.hash_rows = await _count_rows(db_conn, "hash", missing)
                stats.file_rows = await _count_rows(db_conn, "files", missing)
            return stats

        # Foreign keys are never enabled at runtime, so deletes do not cascade. `hash` has to go first
        # to make sure we never leave a hash row pointing at a files row that no longer exists
        async with self.db.writer() as db_conn:
            stats.hash_rows = await _delete_rows(db_conn, "hash", missing)
            stats.file_rows = await _delete_rows(db_conn, "files", missing)
            await db_conn.commit()

        return stats

    async def insert_or_update_hash_db(
        self,
        hash_value: str,
        hash_algo: str,
        file: Path | str,
        original_filename: str | None,
        referer: AbsoluteHttpURL | None,
    ) -> None:
        await self.insert_or_update_hashes(hash_value, hash_algo, file)
        await self.insert_or_update_file(original_filename, referer, file)

    async def insert_or_update_hashes(self, hash_value: str, hash_type: str, file: Path | str) -> None:
        query = """
        INSERT INTO hash (
          hash, hash_type, folder, download_filename
        )
        VALUES
          (?, ?, ?, ?) ON CONFLICT(
            download_filename, folder, hash_type
          ) DO
        UPDATE
        SET
          hash = ?;
        """

        full_path = self.cwd / file
        download_filename = full_path.name
        folder = str(full_path.parent)
        async with self.db.writer() as db_conn:
            await db_conn.execute(query, (hash_value, hash_type, folder, download_filename, hash_value))
            await db_conn.commit()

    async def insert_or_update_file(
        self,
        original_filename: str | None,
        referer: AbsoluteHttpURL | str | None,
        file: Path | str,
    ) -> None:
        query = """
        INSERT INTO files (
          folder, original_filename, download_filename,
          file_size, referer, date
        )
        VALUES
          (?, ?, ?, ?, ?, ?) ON CONFLICT(download_filename, folder) DO
        UPDATE
        SET
          original_filename = ?,
          file_size = ?,
          referer = ?,
          date = ?;
        """
        referer_ = str(referer) if referer else None
        full_path = self.cwd / file
        download_filename = full_path.name
        folder = str(full_path.parent)
        stat = await aio.stat(full_path)
        file_size = stat.st_size
        file_date = int(stat.st_mtime)
        async with self.db.writer() as db_conn:
            await db_conn.execute(
                query,
                (
                    folder,
                    original_filename,
                    download_filename,
                    file_size,
                    referer_,
                    file_date,
                    original_filename,
                    file_size,
                    referer_,
                    file_date,
                ),
            )
            await db_conn.commit()


@aio.to_thread
def _filter_missing(files: Sequence[_FileKey]) -> list[_FileKey]:
    # A single thread hop for the whole database. `os.path` instead of `pathlib` because a large
    # library means hundreds of thousands of these, and building a Path for each one is not free
    return [file for file in files if not os.path.exists(os.path.join(*file))]  # noqa: PTH110, PTH118


def _chunks(files: Sequence[_FileKey]) -> Generator[Sequence[_FileKey]]:
    for index in range(0, len(files), _CHUNK_SIZE):
        yield files[index : index + _CHUNK_SIZE]


def _where_in(chunk: Sequence[_FileKey]) -> tuple[str, list[str]]:
    values = ", ".join(["(?, ?)"] * len(chunk))
    params = [value for file in chunk for value in file]
    return f"WHERE (folder, download_filename) IN (VALUES {values})", params


async def _delete_rows(db_conn: aiosqlite.Connection, table: str, files: Sequence[_FileKey]) -> int:
    deleted = 0
    for chunk in _chunks(files):
        where, params = _where_in(chunk)
        cursor = await db_conn.execute(f"DELETE FROM {table} {where};", params)  # noqa: S608
        deleted += cursor.rowcount
    return deleted


async def _count_rows(db_conn: aiosqlite.Connection, table: str, files: Sequence[_FileKey]) -> int:
    count = 0
    for chunk in _chunks(files):
        where, params = _where_in(chunk)
        cursor = await db_conn.execute(f"SELECT COUNT(*) AS count FROM {table} {where};", params)  # noqa: S608
        row = await cursor.fetchone()
        assert row is not None
        count += row["count"]
    return count
