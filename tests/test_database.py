from __future__ import annotations

from pathlib import Path

import pytest

from cyberdrop_dl import aio, scrape_mapper
from cyberdrop_dl.crawlers.crawler import _prepare_download_path
from cyberdrop_dl.database import Database, common, schema
from cyberdrop_dl.exceptions import DatabaseError
from cyberdrop_dl.scrape_source import _create_item_from_row
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import parse_url

_MOCK_ROW = {
    "referer": "https://drive.google.com/file/d/1F0YBsnQRvrMbK0p9UlnyLu88kqQ0j_F6/edit",
    "download_path": "/cdl/downloads",
    "completed_at": None,
    "created_at": None,
}


@pytest.fixture
def item() -> ScrapeItem:
    return ScrapeItem(url=AbsoluteHttpURL("https://drive.google.com"))


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://megacloud.blog/embed-2/v3/e-1/TZb4gRkOQ642?k=1&autoPlay=1&oa=0&asi=1",
            "/embed-2/v3/e-1/TZb4gRkOQ642",
        ),
        (
            "https://www.mediafire.com/file/ctppmpm7giofsgv/ADOFAI.vpk",
            "ADOFAI.vpk",
        ),
        (
            "https://mega.nz/#!Ue5VRSIQ!kC2E4a4JwfWWCWYNJovGFHlbz8F",
            "/#!Ue5VRSIQ!kC2E4a4JwfWWCWYNJovGFHlbz8F",
        ),
        (
            "https://mega.nz/folder/oZZxyBrY#oU4jASLPpJVvqGHJIMRcgQ/file/IYZABDGY",
            "/folder/oZZxyBrY#oU4jASLPpJVvqGHJIMRcgQ/file/IYZABDGY",
        ),
        (
            "https://c.bunkr-cache.se/HwdRnHMUiWOQevCg/1df93418-5063-4e1b-851e-9470cb8fc5c6.mp4",
            "/1df93418-5063-4e1b-851e-9470cb8fc5c6.mp4",
        ),
        (
            "https://e-hentai.network/h/1bb8b499a5a1a21f9e25e2c42513f310c20e83a9-115314-1280-720-wbp/keystamp=1763995200-3f6832af21;fileindex=169742365;xres=1280/1_2.webp",
            "/h/1bb8b499a5a1a21f9e25e2c42513f310c20e83a9-115314-1280-720-wbp",
        ),
        (
            "https://app.koofr.net/content/links/0a00467b-2901-4213-8d71-44fad80de82d/files/get/Cyberdrop-DL.v8.4.0.zip?path=/Cyberdrop-DL.v8.4.0.zip",
            "/content/links/0a00467b-2901-4213-8d71-44fad80de82d/files/get/Cyberdrop-DL.v8.4.0.zip?path=/Cyberdrop-DL.v8.4.0.zip",
        ),
        (
            "https://transfer.it/cs/g?x=yhWbjogXxRLL&n=qgxVBD5D&fn=start_linux.sh",
            "/cs/g?x=yhWbjogXxRLL&n=qgxVBD5D&fn=start_linux.sh",
        ),
    ],
)
def test_create_db_path(url: str, expected: str) -> None:
    crawlers = scrape_mapper.get_crawlers_mapping()
    url_ = parse_url(url)
    crawler = scrape_mapper._best_match(crawlers, url_.host)
    assert crawler
    path = crawler.__db_path__(url_)
    assert path == expected


class TestGetDownloadPath:
    def test_loose_file(self, item: ScrapeItem) -> None:
        assert not item.folders
        assert not item.part_of_album
        assert item.path == Path()
        download_path = _prepare_download_path(item, "cyberdrop")
        assert download_path == Path("downloads/Loose Files (cyberdrop)")

    def test_loose_file_with_parent(self, item: ScrapeItem) -> None:
        item.append_folders("a/sub/folder")
        download_path = _prepare_download_path(item, "cyberdrop")
        assert download_path == Path("downloads/a-sub-folder/Loose Files (cyberdrop)")

    def test_album_file(self, item: ScrapeItem) -> None:
        item.append_folders("a/sub/folder")
        item.part_of_album = True
        download_path = _prepare_download_path(item, "cyberdrop")
        assert download_path == Path("downloads/a-sub-folder")

    def test_retry_path(self, item: ScrapeItem) -> None:
        item.append_folders("a/sub/folder")
        item.part_of_album = True


async def test_database_creation(tmp_cwd: Path) -> None:
    db_file = tmp_cwd / "test_db.db"
    db = Database(db_file)
    async with db:
        pass

    assert db.is_new
    size = await aio.get_size(db_file)
    assert size
    assert db.schema.up_to_date


async def test_pre_allocation(tmp_cwd: Path) -> None:
    db_file = tmp_cwd / "test_db.db"
    async with common.connect(db_file) as db:
        size = await aio.get_size(db_file)
        assert size == 0

    async with common.connect(db_file) as db:
        await common.pre_allocate_100mb(db)

    size = await aio.get_size(db_file)
    assert size
    assert size >= 100e6


async def test_database_version_check(tmp_cwd: Path) -> None:
    db_file = tmp_cwd / "test_db.db"
    db_file.touch()
    async with Database(db_file).connect() as db:
        await db._create_tables()
        assert db.is_new
        await db.conn.execute("DROP TABLE 'schema_version'")
        await db.conn.commit()

    async with Database(db_file).connect() as db:
        assert not db.is_new
        assert not db.schema.up_to_date
        await db.schema.create()
        assert db.schema.version is None
        assert await db.schema.get_version() is None
        version = schema.Version(8, 8, 8)
        await db.schema.update(version)
        assert not db.schema.up_to_date
        assert await db.schema.get_version() == version
        assert db.schema.version == version
        with pytest.raises(DatabaseError):
            db.schema.check_version()


async def test_db_schema_dump(tmp_cwd: Path) -> None:
    db_file = tmp_cwd / "test_db.db"

    async with Database(db_file) as db:
        current_schema = await schema.dump(db.conn)

    assert current_schema == schema.V9_15_0


def test_create_item_from_row() -> None:
    referer, domain, url_path, download_path, download_filename = (
        "https://example.com/a/b/c/",
        "example.com",
        "/a/b/c",
        "/home/user/downloads",
        "movie.mp4",
    )

    item = _create_item_from_row(locals())
    assert item.url.human_repr() == referer
    assert item.part_of_album is True
    info = item.retry_info
    assert info
    assert info.domain == domain
    assert info.url_path == url_path
    assert info.download_path == Path(download_path)
    assert info.download_filename == download_filename
