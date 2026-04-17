from __future__ import annotations

from unittest import mock

import pytest
from bs4 import BeautifulSoup

from cyberdrop_dl.crawlers.bunkrr import (
    BunkrrCrawler,
    File,
    _album_page_url,
    _get_album_last_page,
    _get_download_button_details,
    _get_related_album_url,
)
from cyberdrop_dl.data_structures import AbsoluteHttpURL
from cyberdrop_dl.data_structures.url_objects import ScrapeItem
from cyberdrop_dl.exceptions import ScrapeError
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


def test_get_download_button_details_raises_scrape_error_without_href() -> None:
    soup = BeautifulSoup('<a class="btn btn-main ic-download-01">Download</a>', "html.parser")

    with pytest.raises(ScrapeError):
        _get_download_button_details(
            soup,
            _parse_with_base,
            AbsoluteHttpURL("https://bunkr.cr"),
        )


def test_album_page_url_normalizes_existing_page_query() -> None:
    url = AbsoluteHttpURL("https://bunkr.cr/a/fQ6HHKtg?page=3")

    assert _album_page_url(url, 1) == AbsoluteHttpURL("https://bunkr.cr/a/fQ6HHKtg?advanced=1")
    assert _album_page_url(url, 6) == AbsoluteHttpURL("https://bunkr.cr/a/fQ6HHKtg?advanced=1&page=6")


def test_get_album_last_page_reads_pagination_links() -> None:
    soup = BeautifulSoup(
        """
        <nav>
            <a href="/a/fQ6HHKtg?page=2">2</a>
            <a href="/a/fQ6HHKtg?page=6">6</a>
            <a href="/a/different?page=99">unrelated</a>
        </nav>
        """,
        "html.parser",
    )

    last_page = _get_album_last_page(
        soup,
        _parse_with_base,
        AbsoluteHttpURL("https://bunkr.cr/a/fQ6HHKtg"),
    )

    assert last_page == 6


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


async def test_album_scrapes_paginated_album_pages() -> None:
    crawler = BunkrrCrawler(mock.Mock())
    url = AbsoluteHttpURL("https://bunkr.cr/a/fQ6HHKtg")
    page_1 = BeautifulSoup(
        """
        <html>
            <head><meta property="og:title" content="Bunkr Album"></head>
            <body><a href="/a/fQ6HHKtg?page=2">2</a></body>
        </html>
        """,
        "html.parser",
    )
    page_2 = BeautifulSoup(
        """
        <html>
            <head><meta property="og:title" content="Bunkr Album"></head>
            <body></body>
        </html>
        """,
        "html.parser",
    )
    first_file = File(name="one.mp4", thumbnail="", date="12:00:00 01/01/2024", slug="one.mp4")
    second_file = File(name="two.mp4", thumbnail="", date="12:00:00 01/01/2024", slug="two.mp4")
    scheduled_coroutines = []

    def close_scheduled_coroutine(coro):
        scheduled_coroutines.append(coro)
        coro.close()

    crawler._request_soup_lenient = mock.AsyncMock(side_effect=[page_1, page_2])
    crawler.get_album_results = mock.AsyncMock(return_value={})
    crawler.create_title = mock.Mock(return_value="Bunkr Album")
    crawler._parse_album_files = mock.Mock(side_effect=[iter([first_file]), iter([second_file])])
    crawler._album_file = mock.AsyncMock()
    crawler.create_task = mock.Mock(side_effect=close_scheduled_coroutine)

    scrape_item = ScrapeItem(url=url)
    await crawler._album(scrape_item, "fQ6HHKtg")

    requested_urls = [call.args[0] for call in crawler._request_soup_lenient.await_args_list]
    child_urls = [call.args[0].url for call in crawler._album_file.call_args_list]
    assert requested_urls == [
        AbsoluteHttpURL("https://bunkr.cr/a/fQ6HHKtg?advanced=1"),
        AbsoluteHttpURL("https://bunkr.cr/a/fQ6HHKtg?advanced=1&page=2"),
    ]
    assert child_urls == [
        AbsoluteHttpURL("https://bunkr.cr/f/one.mp4"),
        AbsoluteHttpURL("https://bunkr.cr/f/two.mp4"),
    ]
    assert scrape_item.children == 2
    assert len(scheduled_coroutines) == 2


async def test_album_continues_when_later_page_reveals_more_pages() -> None:
    crawler = BunkrrCrawler(mock.Mock())
    url = AbsoluteHttpURL("https://bunkr.cr/a/fQ6HHKtg")
    page_1 = BeautifulSoup(
        """
        <html>
            <head><meta property="og:title" content="Bunkr Album"></head>
            <body><a href="/a/fQ6HHKtg?page=2">2</a></body>
        </html>
        """,
        "html.parser",
    )
    page_2 = BeautifulSoup('<html><a href="/a/fQ6HHKtg?page=3">3</a></html>', "html.parser")
    page_3 = BeautifulSoup("<html></html>", "html.parser")
    files = [
        File(name="one.mp4", thumbnail="", date="12:00:00 01/01/2024", slug="one.mp4"),
        File(name="two.mp4", thumbnail="", date="12:00:00 01/01/2024", slug="two.mp4"),
        File(name="three.mp4", thumbnail="", date="12:00:00 01/01/2024", slug="three.mp4"),
    ]

    crawler._request_soup_lenient = mock.AsyncMock(side_effect=[page_1, page_2, page_3])
    crawler.get_album_results = mock.AsyncMock(return_value={})
    crawler.create_title = mock.Mock(return_value="Bunkr Album")
    crawler._parse_album_files = mock.Mock(side_effect=[iter([files[0]]), iter([files[1]]), iter([files[2]])])
    crawler._album_file = mock.AsyncMock()
    crawler.create_task = mock.Mock(side_effect=lambda coro: coro.close())

    await crawler._album(ScrapeItem(url=url), "fQ6HHKtg")

    requested_urls = [call.args[0] for call in crawler._request_soup_lenient.await_args_list]
    assert requested_urls == [
        AbsoluteHttpURL("https://bunkr.cr/a/fQ6HHKtg?advanced=1"),
        AbsoluteHttpURL("https://bunkr.cr/a/fQ6HHKtg?advanced=1&page=2"),
        AbsoluteHttpURL("https://bunkr.cr/a/fQ6HHKtg?advanced=1&page=3"),
    ]


async def test_album_file_uses_album_results_before_referer_lookup() -> None:
    manager = mock.Mock()
    manager.states.RUNNING.wait = mock.AsyncMock()
    manager.progress_manager.scraping_progress.add_task.return_value = 1
    crawler = BunkrrCrawler(manager)
    file = File(
        name="one.mp4",
        thumbnail="https://i-bunkr-test.bunkr.ru/thumbs/one.jpg",
        date="12:00:00 01/01/2024",
        slug="one.mp4",
    )
    src = AbsoluteHttpURL("https://bunkr-test.bunkr.ru/one.mp4")
    results = {crawler.create_db_path(src): 1}

    crawler.check_complete_from_referer = mock.AsyncMock(return_value=False)
    crawler._direct_file = mock.AsyncMock()
    crawler.create_task = mock.Mock()

    await crawler._album_file(ScrapeItem(url=AbsoluteHttpURL("https://bunkr.cr/f/one.mp4")), file, results)

    crawler.check_complete_from_referer.assert_not_awaited()
    crawler._direct_file.assert_not_awaited()
    crawler.create_task.assert_not_called()


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
