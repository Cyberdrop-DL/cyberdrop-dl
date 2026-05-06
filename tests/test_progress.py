import pytest

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
