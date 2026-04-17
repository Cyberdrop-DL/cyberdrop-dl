from __future__ import annotations

from unittest import mock

from bs4 import BeautifulSoup

from cyberdrop_dl.crawlers.bunkrr import BunkrrCrawler, _get_download_button_details, _get_related_album_url
from cyberdrop_dl.data_structures import AbsoluteHttpURL
from cyberdrop_dl.data_structures.url_objects import ScrapeItem
from cyberdrop_dl.utils.utilities import parse_url


def _parse_with_base(link: str, relative_to: AbsoluteHttpURL | None) -> AbsoluteHttpURL:
    assert relative_to is not None
    return parse_url(link, relative_to)


def test_get_download_button_details_reads_file_id() -> None:
    soup = BeautifulSoup(
        '<a id="download-btn" class="btn btn-main ic-download-01" href="#" data-id="11234941">Download</a>',
        "html.parser",
    )

    file_id, download_url = _get_download_button_details(
        soup,
        _parse_with_base,
        AbsoluteHttpURL("https://get.bunkrr.su"),
    )

    assert file_id == "11234941"
    assert download_url is None


def test_get_download_button_details_reads_reinforced_href() -> None:
    soup = BeautifulSoup(
        '<a class="btn btn-main ic-download-01" href="https://get.bunkrr.su/file/11234941">Download</a>',
        "html.parser",
    )

    file_id, download_url = _get_download_button_details(
        soup,
        _parse_with_base,
        AbsoluteHttpURL("https://bunkr.cr"),
    )

    assert file_id is None
    assert download_url == AbsoluteHttpURL("https://get.bunkrr.su/file/11234941")


def test_get_related_album_url_reads_file_page_album_link() -> None:
    soup = BeautifulSoup(
        '<h2 class="files-album">More files in this <a href="../a/eccmqVJi">album</a></h2>',
        "html.parser",
    )

    album_url = _get_related_album_url(
        soup,
        _parse_with_base,
        AbsoluteHttpURL("https://bunkr.cr/f/8-16-8out556m95_30UUdVDDAQ-HnEfe1zW.mp4"),
    )

    assert album_url == AbsoluteHttpURL("https://bunkr.cr/a/eccmqVJi")


async def test_top_level_file_expands_related_album() -> None:
    crawler = BunkrrCrawler(mock.Mock())
    file_url = AbsoluteHttpURL("https://bunkr.cr/f/8-16-8out556m95_30UUdVDDAQ-HnEfe1zW.mp4")
    soup = BeautifulSoup(
        """
        <html>
            <head><meta property="og:title" content="8 16 8out556m95_30UUdVDDAQ.mp4"></head>
            <body>
                <h2 class="files-album">More files in this <a href="../a/eccmqVJi">album</a></h2>
                <a class="btn btn-main ic-download-01" href="https://get.bunkrr.su/file/11234941">Download</a>
            </body>
        </html>
        """,
        "html.parser",
    )

    crawler._album = mock.AsyncMock()

    expanded = await crawler._try_related_album(ScrapeItem(url=file_url), soup)

    assert expanded is True
    crawler._album.assert_awaited_once()
    album_item, album_id = crawler._album.await_args.args
    assert album_item.url == AbsoluteHttpURL("https://bunkr.cr/a/eccmqVJi")
    assert album_item.parents == [file_url]
    assert album_id == "eccmqVJi"
