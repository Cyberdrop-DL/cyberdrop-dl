from __future__ import annotations

from types import SimpleNamespace

import aiosqlite

from cyberdrop_dl.data_structures import AbsoluteHttpURL
from cyberdrop_dl.database.tables.history import HistoryTable


async def _create_history_table() -> tuple[HistoryTable, aiosqlite.Connection]:
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    table = HistoryTable(SimpleNamespace(_db_conn=conn, ignore_history=False))
    await table.startup()
    return table, conn


async def test_history_table_creates_lookup_indexes() -> None:
    _, conn = await _create_history_table()

    cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'media'")
    index_names = {row["name"] for row in await cursor.fetchall()}

    assert "idx_media_referer_domain_completed" in index_names
    assert "idx_media_domain_album_completed" in index_names
    assert "idx_media_download_filename" in index_names
    await conn.close()


async def test_check_complete_by_referer_only_needs_one_completed_match() -> None:
    table, conn = await _create_history_table()
    referer = AbsoluteHttpURL("https://bunkr.site/f/one.mp4")
    await conn.executemany(
        """
        INSERT INTO media (domain, url_path, referer, album_id, download_path,
        download_filename, original_filename, completed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("bunkr", "/one.mp4", str(referer), "album", "downloads", "one.mp4", "one.mp4", 0),
            ("bunkr", "/two.mp4", str(referer), "album", "downloads", "two.mp4", "two.mp4", 1),
        ],
    )
    await conn.commit()

    assert await table.check_complete_by_referer("bunkr", referer) is True
    assert await table.check_complete_by_referer("gofile", referer) is False
    await conn.close()
