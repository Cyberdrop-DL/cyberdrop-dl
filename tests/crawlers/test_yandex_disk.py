from __future__ import annotations

import asyncio
from typing import Any
from unittest import mock

import pytest

from cyberdrop_dl.crawlers import yandex_disk
from cyberdrop_dl.url_objects import AbsoluteHttpURL


def _crawler() -> yandex_disk.YandexDiskCrawler:
    crawler = object.__new__(yandex_disk.YandexDiskCrawler)
    crawler.__post_init__()
    return crawler


def _mock_log() -> mock._patch[mock.PropertyMock]:
    return mock.patch.object(yandex_disk.YandexDiskCrawler, "log", new_callable=mock.PropertyMock)


def _file(sk: str) -> yandex_disk.YandexFile:
    return yandex_disk.YandexFile(
        name="video.mp4",
        modified=0,
        type="file",
        id="AbCdEf123",
        path="hash==",
        sk=sk,
        short_url=AbsoluteHttpURL("https://yadi.sk/i/AbCdEf123"),
    )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://disk.yandex.com/i/AbCdEf123", "https://disk.yandex.com"),
        ("https://disk.yandex.com.tr/d/AbCdEf123/video.mp4", "https://disk.yandex.com.tr"),
        ("https://disk.yandex.ru/i/AbCdEf123", "https://disk.yandex.ru"),
    ],
)
def test_download_url_headers_origin(url: str, expected: str) -> None:
    referer = AbsoluteHttpURL("https://yadi.sk/i/AbCdEf123")
    headers = yandex_disk._download_url_headers(AbsoluteHttpURL(url), referer)
    assert headers["Origin"] == expected
    assert headers["Referer"] == headers["X-Retpath-Y"] == str(referer)


def test_raise_for_wrong_sk() -> None:
    with pytest.raises(yandex_disk._WrongSkError) as exc_info:
        yandex_disk._raise_for_wrong_sk({"error": True, "wrongSk": True, "newSk": "y2"})
    assert exc_info.value.new_sk == "y2"


@pytest.mark.parametrize(
    "json_resp",
    [
        {"error": True},
        {"error": True, "wrongSk": True},
        {"error": False, "statusCode": 200, "data": {"url": "https://downloader.disk.yandex.com/disk/x"}},
        ["not", "a", "dict"],
    ],
)
def test_raise_for_wrong_sk_ignores_other_responses(json_resp: Any) -> None:
    yandex_disk._raise_for_wrong_sk(json_resp)


async def test_request_download_url_retries_with_new_sk() -> None:
    crawler = _crawler()
    ok_resp = {"error": False, "data": {"url": "https://downloader.disk.yandex.com/disk/x"}}
    post = mock.AsyncMock(side_effect=[yandex_disk._WrongSkError("y2"), ok_resp])
    url = AbsoluteHttpURL("https://disk.yandex.com/i/AbCdEf123")

    with mock.patch.object(crawler, "_post_download_url", post), _mock_log():
        assert await crawler._request_download_url(url, _file("y1")) == ok_resp

    assert [call.args[1].sk for call in post.await_args_list] == ["y1", "y2"]


async def test_request_download_url_gives_up_after_max_retries() -> None:
    crawler = _crawler()
    post = mock.AsyncMock(side_effect=yandex_disk._WrongSkError("y2"))
    url = AbsoluteHttpURL("https://disk.yandex.com/i/AbCdEf123")

    with (
        mock.patch.object(crawler, "_post_download_url", post),
        _mock_log(),
        pytest.raises(yandex_disk._WrongSkError),
    ):
        await crawler._request_download_url(url, _file("y1"))

    assert post.await_count == yandex_disk._MAX_SK_RETRIES + 1


async def test_first_page_of_a_host_sets_the_session_before_the_rest() -> None:
    crawler = _crawler()
    events: list[str] = []
    in_flight = max_in_flight = 0

    async def request_soup(url: AbsoluteHttpURL, **_: Any) -> None:
        nonlocal in_flight, max_in_flight
        events.append(f"start {url.name}")
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        events.append(f"end {url.name}")

    urls = [AbsoluteHttpURL(f"https://disk.yandex.com/i/{n}") for n in range(4)]
    with mock.patch.object(crawler, "request_soup", request_soup):
        await asyncio.gather(*(crawler._request_page(url) for url in urls))

    assert events[:2] == ["start 0", "end 0"]
    assert max_in_flight == len(urls) - 1
