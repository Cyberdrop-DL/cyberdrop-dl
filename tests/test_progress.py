from unittest import mock

import pytest

from cyberdrop_dl import __version__
from cyberdrop_dl.progress.scraping import ScrapingUI, downloads
from cyberdrop_dl.progress.scraping.errors import UIError
from cyberdrop_dl.url_objects import AbsoluteHttpURL


@pytest.mark.parametrize(
    ("name", "expected_msg", "expected_code"),
    [
        ("404 Not Found", "Not Found", 404),
        ("Unknown", "Unknown", None),
        ("Unknown URL Path", "Unknown URL Path", None),
        ("Max Children Reached", "Max Children Reached", None),
        ("502 Bad Gateway", "Bad Gateway", 502),
        ("Password Protected", "Password Protected", None),
    ],
)
def test_ui_error_parsing(name: str, expected_msg: str, expected_code: int | None) -> None:
    assert UIError.parse(name, count=0) == UIError(expected_msg, 0, expected_code)


@pytest.mark.parametrize(
    ("msg", "code", "padding", "expected"),
    [
        ("Not Found", 404, 0, "404 Not Found"),
        ("Unknown", None, 0, "Unknown"),
        ("Max Children Reached", None, 0, "Max Children Reached"),
        ("Bad Gateway", 502, 0, "502 Bad Gateway"),
        ("Bad Gateway", 502, 2, "502 Bad Gateway"),
        ("Bad Gateway", 502, 3, "502 Bad Gateway"),
        ("Bad Gateway", 502, 5, "  502 Bad Gateway"),
    ],
)
def test_ui_errors_formatting(msg: str, code: int | None, padding: int, expected: str) -> None:
    error = UIError(msg, 0, code)
    assert error.format(padding) == expected + ": 0"


def test_scraping_json_dump() -> None:
    ui = ScrapingUI()

    url = AbsoluteHttpURL("https://example.com/a file.mp4")
    with (
        ui(force=True),
        ui.scrape.new("example.com"),
        ui.downloads.download_file(url.name, url.host, 200, url=url),
    ):
        ui.download_errors.add("450 An Error")
        dump = ui.__json__()
        assert dump["files"] == {
            "completed": 0,
            "previously_completed": 0,
            "skipped": 0,
            "failed": 0,
            "queued": 0,
        }
        assert dump["scrape_errors"] == {
            "errors": (),
            "sent_to_jdownloader": 0,
            "skipped": 0,
        }
        assert dump["download_errors"] == {
            "errors": (
                {
                    "msg": "An Error",
                    "count": 1,
                    "code": 450,
                },
            ),
        }
        assert dump["scraping"] == (
            {
                "url": "example.com",
                "elapsed": mock.ANY,
            },
        )
        assert dump["downloads"] == (
            {
                "speed": None,
                "size": 200,
                "completed": 0,
                "hls": False,
                "bytes_downloaded": 0,
                "domain": "EXAMPLE.COM",
                "description": "a file.mp4",
                "url": str(url),
                "eta": None,
                "visible": True,
            },
        )

        assert dump["status"] == {
            "description": f"cyberdrop-dl v{__version__}",
            "messages": (),
        }


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("a video[avc1][1080p].mp4", "a video[avc1][1080p].mp4"),
        ("丸の内OLレイナ [12345].mp4", "OL [12345].mp4"),
    ],
)
def test_download_file_escaping(filename: str, expected: str) -> None:
    result = downloads._escape_filename(filename)
    assert result == expected
