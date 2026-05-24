import pytest

from cyberdrop_dl.crawlers.onefichier import _get_file_id
from cyberdrop_dl.url_objects import AbsoluteHttpURL


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://1fichier.com?jfnofl25jgnpec1ybgcx&af=3797078", "jfnofl25jgnpec1ybgcx"),
        ("https://1fichier.com?jfnofl25jgnpec1ybgcx", "jfnofl25jgnpec1ybgcx"),
        ("https://1fichier.com?jfno&af=3797078", None),
    ],
)
def test_get_file_id(url: str, expected: str | None) -> None:
    result = _get_file_id(AbsoluteHttpURL(url).query)
    assert result == expected
