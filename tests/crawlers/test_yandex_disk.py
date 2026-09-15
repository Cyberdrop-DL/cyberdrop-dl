from typing import Any

import pytest

from cyberdrop_dl.crawlers import yandex_disk
from cyberdrop_dl.url_objects import AbsoluteHttpURL


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
