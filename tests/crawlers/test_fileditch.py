import base64

import pytest

from cyberdrop_dl.crawlers import fileditch
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL


def _token(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://goonditch.com/beta22/abc/file.mkv?exp=1787436084&sig=abc", "/beta22/abc/file.mkv"),
        ("https://goonditch.com/alpha7/abc/file.mp4?md5=abc&expires=1787436084", "/alpha7/abc/file.mp4"),
        (
            "https://beta.goonditch.st/" + _token("1787436084:AbC-dEf_123:577/alpha35/abc/file.mp4"),
            "/alpha35/abc/file.mp4",
        ),
        (
            "https://delta.goonditch.st/" + _token("1787436084:AbC-dEf_123:577/beta5/abc/%5B8.11%5D_valk1.mp4"),
            "/beta5/abc/%5B8.11%5D_valk1.mp4",
        ),
        (
            "https://beta.goonditch.st/" + _token("1787436084:AbC-dEf_123:577/s21/FHVZKQyAZlIsrneDAsp.jpeg"),
            fileditch._HOMEPAGE_CATCH_ALL,
        ),
    ],
)
def test_file_path(url: str, expected: str) -> None:
    assert fileditch._file_path(AbsoluteHttpURL(url)) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://goonditch.com/beta22/abc/file.mkv",
        "https://goonditch.com/beta22/abc/file.mkv?exp=1787436084",
        "https://goonditch.com/file.mkv",
        "https://beta.goonditch.st/" + _token("AbC-dEf_123:577/alpha35/abc/file.mp4"),
        "https://beta.goonditch.st/" + _token("1787436084::577/alpha35/abc/file.mp4"),
        "https://beta.goonditch.st/" + _token("1787436084:AbC-dEf_123:file.mp4"),
        "https://beta.goonditch.st/a/" + _token("1787436084:AbC-dEf_123:577/alpha35/abc/file.mp4"),
    ],
)
def test_file_path_rejects_unsigned_urls(url: str) -> None:
    with pytest.raises(ScrapeError):
        fileditch._file_path(AbsoluteHttpURL(url))


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://fileditchvids.st/beta22/abc/file.mkv?fdrh=1787436084.aHR0cHM6Ly9maWxlZGl0Y2hmaWxlcy5tZQ.abc123",
            "https://fileditchvids.st/beta22/abc/file.mkv",
        ),
        ("https://fileditchfiles.me/file.php?f=/b71/file.mp4", "https://fileditchfiles.me/b71/file.mp4"),
        (
            "https://fileditchfiles.me/beta5/abc/%5B8.11%5D_valk1.mp4",
            "https://fileditchfiles.me/beta5/abc/%5B8.11%5D_valk1.mp4",
        ),
        ("https://theditch.st/wtk8hvwb", "https://theditch.st/wtk8hvwb"),
    ],
)
def test_transform_url(url: str, expected: str) -> None:
    result = str(fileditch.FileditchCrawler.transform_url(AbsoluteHttpURL(url)))
    assert result == expected
