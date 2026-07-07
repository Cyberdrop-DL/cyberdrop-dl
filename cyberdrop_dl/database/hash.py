from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast

from cyberdrop_dl import aio

from .common import Table
from .definitions import CREATE_FILES, CREATE_HASH, CREATE_HASH_INDEX

if TYPE_CHECKING:
    import aiosqlite

    from cyberdrop_dl.url_objects import AbsoluteHttpURL


logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class HashTable(Table, name="hash"):
    cwd: Path = dataclasses.field(init=False, default_factory=lambda: Path.cwd().expanduser().resolve())

    async def create(self) -> None:
        for query in (
            CREATE_FILES,
            CREATE_HASH,
            CREATE_HASH_INDEX,
        ):
            _ = await self.db_conn.execute(query)

        await self.db_conn.commit()

    async def get_file_hash_exists(self, path: Path | str, hash_type: str) -> str | None:
        query = "SELECT hash FROM hash WHERE folder= ? AND download_filename= ? AND hash_type= ? AND hash IS NOT NULL LIMIT 1;"
        path = self.cwd / path
        folder = str(path.parent)
        filename = path.name
        cursor = await self.db_conn.execute(query, (folder, filename, hash_type))
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

        rows = await self.db_conn.execute_fetchall(query, (hash_value, size, hash_algo))
        return cast("list[aiosqlite.Row]", rows)

    async def check_hash_exists(self, hash_type: str, hash_value: str) -> bool:
        if self.ignore_history:
            return False

        query = "SELECT 1 FROM hash WHERE hash.hash_type = ? AND hash.hash = ? LIMIT 1;"
        cursor = await self.db_conn.execute(query, (hash_type, hash_value))
        return await cursor.fetchone() is not None

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
        await self.db_conn.execute(query, (hash_value, hash_type, folder, download_filename, hash_value))
        await self.db_conn.commit()

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
        await self.db_conn.execute(
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
        await self.db_conn.commit()
