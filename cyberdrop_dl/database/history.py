from __future__ import annotations

import contextlib
import logging
import time
from sqlite3 import IntegrityError
from typing import TYPE_CHECKING, Any

from .common import Table
from .definitions import CREATE_HISTORY, CREATE_MEDIA_INDEX

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    import aiosqlite

    from cyberdrop_dl.crawlers.crawler import Crawler
    from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem


_FETCH_MANY_SIZE: int = 1000
logger = logging.getLogger(__name__)


class HistoryTable(Table, name="media"):
    async def create(self) -> None:
        await self.db_conn.execute(CREATE_HISTORY)
        await self.db_conn.executescript(CREATE_MEDIA_INDEX)
        await self.db_conn.commit()

    async def apply_updates(self) -> None:
        logger.info("Applying database updates. This could take a while...")
        await apply_fixes(self.db_conn)

    async def check_complete(self, domain: str, db_path: str) -> tuple[str, bool]:
        """Checks whether an individual file has completed given its domain and url path."""
        if self.ignore_history:
            return "", False

        query = "SELECT referer, completed FROM media WHERE domain = ? and url_path = ? LIMIT 1;"
        cursor = await self.db_conn.execute(query, (domain, db_path))
        if row := await cursor.fetchone():
            return row["referer"], bool(row["completed"])
        return "", False

    async def update_referer(self, domain: str, db_path: str, referer: AbsoluteHttpURL) -> None:
        query = "UPDATE media SET referer = ? WHERE domain = ? and url_path = ?"
        await self.db_conn.execute(query, (str(referer), domain, db_path))
        await self.db_conn.commit()

    async def query_album(self, domain: str, album_id: str) -> dict[str, bool]:
        if self.ignore_history:
            return {}

        query = "SELECT url_path, completed FROM media WHERE domain = ? and album_id = ?"
        rows = await self.db_conn.execute_fetchall(query, (domain, album_id))
        return {row["url_path"]: bool(row["completed"]) for row in rows}

    async def set_album_id(self, domain: str, media_item: MediaItem) -> None:
        query = "UPDATE media SET album_id = ? WHERE domain = ? and url_path = ?"
        await self.db_conn.execute(query, (media_item.album_id, domain, media_item.db_path))
        await self.db_conn.commit()

    async def check_complete_by_referer(self, domain: str | None, referer: AbsoluteHttpURL) -> bool:
        if self.ignore_history:
            return False

        if domain is None:
            query = "SELECT 1 FROM media WHERE referer = ? AND completed != 0) LIMIT 1"
            params = (str(referer),)
        else:
            query = "SELECT 1 FROM media WHERE domain = ? AND referer = ? AND completed != 0 LIMIT 1"
            params = domain, str(referer)

        cursor = await self.db_conn.execute(query, params)
        return await cursor.fetchone() is not None

    async def insert_incompleted(self, domain: str, media_item: MediaItem) -> None:
        url_path = media_item.db_path
        download_filename = media_item.download_filename or ""
        cursor = await self.db_conn.cursor()
        query = "UPDATE media SET domain = ?, album_id = ? WHERE domain = 'no_crawler' and url_path = ? and referer = ?"
        try:
            await cursor.execute(query, (domain, media_item.album_id, url_path, str(media_item.referer)))
        except IntegrityError:
            delete_query = "DELETE FROM media WHERE domain = 'no_crawler' and url_path = ?"
            await cursor.execute(delete_query, (url_path,))

        insert_query = """
        INSERT OR IGNORE INTO media (
          domain, url_path, referer, album_id,
          download_path, download_filename,
          original_filename, completed, created_at
        )
        VALUES
          (
            ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP
          );
        """

        await cursor.execute(
            insert_query,
            (
                domain,
                url_path,
                str(media_item.referer),
                media_item.album_id,
                str(media_item.download_folder),
                download_filename,
                media_item.original_filename,
                0,
            ),
        )
        if download_filename:
            query = "UPDATE media SET download_filename = ? WHERE domain = ? and url_path = ?"
            await cursor.execute(query, (download_filename, domain, url_path))
        await self.db_conn.commit()

    async def mark_complete(self, domain: str, media_item: MediaItem) -> None:
        query = "UPDATE media SET completed = 1, completed_at = CURRENT_TIMESTAMP WHERE domain = ? and url_path = ?"
        await self.db_conn.execute(query, (domain, media_item.db_path))
        await self.db_conn.commit()

    async def add_filesize(self, domain: str, media_item: MediaItem) -> None:
        url_path = media_item.db_path
        file_size = media_item.path.stat().st_size
        query = """UPDATE media SET file_size=? WHERE domain = ? and url_path = ?"""
        await self.db_conn.execute(query, (file_size, domain, url_path))
        await self.db_conn.commit()

    async def add_duration(self, domain: str, media_item: MediaItem) -> None:
        query = "UPDATE media SET duration=? WHERE domain = ? and url_path = ?"
        await self.db_conn.execute(query, (media_item.duration, domain, media_item.db_path))
        await self.db_conn.commit()

    async def get_duration(self, domain: str, media_item: MediaItem) -> float | None:
        if media_item.is_segment:
            return None

        url_path = media_item.db_path
        query = "SELECT duration FROM media WHERE domain = ? and url_path = ? LIMIT 1"
        cursor = await self.db_conn.execute(query, (domain, url_path))
        if row := await cursor.fetchone():
            return row["duration"]

    async def add_download_filename(self, domain: str, media_item: MediaItem) -> None:
        url_path = media_item.db_path
        query = "UPDATE media SET download_filename=? WHERE domain = ? and url_path = ? and download_filename = ''"
        await self.db_conn.execute(query, (media_item.download_filename, domain, url_path))
        await self.db_conn.commit()

    async def check_filename_exists(self, filename: str) -> bool:
        query = "SELECT 1 FROM media WHERE download_filename = ? LIMIT 1"
        cursor = await self.db_conn.execute(query, (filename,))
        return await cursor.fetchone() is not None

    async def get_downloaded_filename(self, domain: str, media_item: MediaItem) -> str | None:
        """Returns the downloaded filename from the database."""

        if media_item.is_segment:
            return media_item.filename

        url_path = media_item.db_path
        query = "SELECT download_filename FROM media WHERE domain = ? and url_path = ? LIMIT 1"
        cursor = await self.db_conn.execute(query, (domain, url_path))
        if row := await cursor.fetchone():
            return row["download_filename"]


async def apply_fixes(db_conn: aiosqlite.Connection) -> None:
    await _fix_domains(db_conn)
    await _fix_referers(db_conn)


async def _fix_domains(db_conn: aiosqlite.Connection) -> None:
    with _timed_update("old database domains"):
        updates = "\n".join(
            f"UPDATE OR REPLACE media SET domain = '{current}' WHERE domain = '{old}';"  # noqa: S608
            for current, old in [
                ("bunkr", "bunkrr"),
                ("goonbox", "sharex"),
                ("turbovid", "saint"),
                ("nudostar.tv", "nudostartv"),
                ("goonbox", "jpg5.su"),
            ]
        )
        await db_conn.executescript(updates)
        await db_conn.commit()


async def _fix_referers(db_conn: aiosqlite.Connection) -> None:
    from cyberdrop_dl.crawlers import bunkr, cyberdrop, goonbox, redgifs, turbovid

    def try_wrap[T](fn: Callable[..., T]) -> Callable[..., T]:
        def call(*args: Any, **kwargs: Any) -> T:
            try:
                return fn(*args, **kwargs)
            except Exception:
                logger.exception(f"{fn.__name__} failed")
                raise

        return call

    updates = ""
    with _timed_update("old database referers"):
        for fn_name, fn, domain in [
            ("FIX_REDGIFS_REFERER", redgifs.fix_redgifs_referer, "redgifs"),
            ("FIX_GOONBOX_REFERER", _generic_fix_referer(goonbox.GoonBoxCrawler), "goonbox"),
            ("FIX_CYBERDROP_REFERER", _generic_fix_referer(cyberdrop.CyberdropCrawler), "cyberdrop"),
            ("FIX_TURBOVID_REFERER", turbovid.fix_turbovid_referer, "turbovid"),
            ("FIX_BUNKR_REFERER", bunkr.fix_db_referer, "bunkr"),
        ]:
            await db_conn.create_function(fn_name, 1, try_wrap(fn), deterministic=True)
            updates += f"UPDATE OR REPLACE media SET referer = {fn_name}(referer) WHERE domain = '{domain}';"  # noqa: S608

        await db_conn.executescript(updates)
        await db_conn.commit()


@contextlib.contextmanager
def _timed_update(name: str) -> Generator[None]:
    start = time.monotonic()
    logger.info(f"Updating {name}")
    try:
        yield
    finally:
        took = time.monotonic() - start
        logger.info(f"Finished update of {name}. Took: {took:0.2f} seconds")


def _generic_fix_referer(crawler: type[Crawler]) -> Callable[[str], str]:
    def fix_db_referer(referer: str) -> str:
        url = crawler.parse_url(referer, trim=False)
        return str(crawler.transform_url(url))

    fix_db_referer.__name__ = f"fix_{crawler.DOMAIN}_referer"
    return fix_db_referer
