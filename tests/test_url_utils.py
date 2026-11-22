import pytest

from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import urls


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("/a/b/c", ""),
        ("https://example.com/a/b/c", "c"),
        ("https://example.com/a/b/", "b"),
        ("https://example.com/a/b//", ""),
        ("https://example.com/a", "a"),
        ("https://example.com/a/", "a"),
        ("https://example.com/", ""),
        ("https://example.com//", ""),
        ("https://example.com/a/b/c?name=d", "c"),
        ("https://example.com/a/b/c?name=d/e/f", "c"),
        ("https://example.com/a/b/c#d/e/f", "c"),
        ("//example.com/a/b/c?name=d/e/f", "c"),
        ("//example.com/a/b/c#d/e/f", "c"),
        ("a/b/c?name=d/e/f", ""),
        ("/a/b/c#d/e/f", ""),
    ],
)
def test_name_from_url(url: str, expected: str):
    assert urls.name_from_url(AbsoluteHttpURL(url)) == expected
