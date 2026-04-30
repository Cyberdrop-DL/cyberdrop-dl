import pytest

from cyberdrop_dl.managers.manager import _log_errors
from cyberdrop_dl.progress.scraping.errors import UIError


@pytest.mark.parametrize(
    "name, expected_msg, expected_code",
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
    "msg, code, padding, expected",
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
def test_ui_errors_formatting(msg: str, code: int | None, padding: int, expected: str):
    error = UIError(msg, 0, code)
    assert error.format(padding) == expected + ": 0"


@pytest.mark.parametrize(
    "scrape_errors, download_errors, expected_msgs",
    [
        (
            ["Client Connector SSL Error", "502 Bad Gateway"],
            ["1234 Bad Gateway"],
            [
                "------------------------------",
                "Scrape Errors:",
                "       Client Connector SSL Error: 0",
                "   502 Bad Gateway: 0",
                "------------------------------",
                "Download Errors:",
                "  1234 Bad Gateway: 0",
            ],
        ),
        (
            ["Error1", "Error2"],
            ["Error3", "Error4"],
            [
                "------------------------------",
                "Scrape Errors:",
                "  Error1: 0",
                "  Error2: 0",
                "------------------------------",
                "Download Errors:",
                "  Error3: 0",
                "  Error4: 0",
            ],
        ),
        (
            ["Error1", "Error2"],
            ["Error3", "2 Error4", "Error5"],
            [
                "------------------------------",
                "Scrape Errors:",
                "    Error1: 0",
                "    Error2: 0",
                "------------------------------",
                "Download Errors:",
                "    Error3: 0",
                "  2 Error4: 0",
                "    Error5: 0",
            ],
        ),
    ],
)
def test_stats_formating(
    logs: pytest.LogCaptureFixture,
    scrape_errors: tuple[str, ...],
    download_errors: tuple[str, ...],
    expected_msgs: list[str],
) -> None:

    _log_errors(
        tuple(UIError.parse(msg, count=0) for msg in scrape_errors),
        tuple(UIError.parse(msg, count=0) for msg in download_errors),
    )
    assert logs.messages == expected_msgs
