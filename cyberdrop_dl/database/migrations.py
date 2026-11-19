from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3

_MEDIA_TO_FILES_SQL = """
INSERT OR IGNORE INTO files
    (folder, download_filename, original_filename, file_size, referer, date)
SELECT
    download_path,
    download_filename,
    original_filename,
    {file_size},
    referer,
    CAST(strftime('%s', created_at) AS INTEGER)
FROM {media_table}
WHERE download_path IS NOT NULL
"""


def media_to_files_sql(media_table: str, file_size: str = "file_size") -> str:
    return _MEDIA_TO_FILES_SQL.format(media_table=media_table, file_size=file_size)


def transfer_legacy_media(new_conn: sqlite3.Connection, file_size: str) -> None:
    new_conn.execute(media_to_files_sql('old."media"', file_size))
