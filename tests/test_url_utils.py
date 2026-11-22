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
        ("https://example.com/a///b//c//", ""),
        ("https://example.com/a/b/c?name=d", "c"),
        ("https://example.com/a/b/c?name=d/e/f", "c"),
        ("https://example.com/a/b/c#d/e/f", "c"),
        ("//example.com/a/b/c?name=d/e/f", "c"),
        ("//example.com/a/b/c#d/e/f", "c"),
        ("a/b/c?name=d/e/f", ""),
        ("/a/b/c#d/e/f", ""),
    ],
)
def test_name_from_url(url: str, expected: str) -> None:
    urlo = AbsoluteHttpURL(url)
    assert urls.name_from_url(urlo) == expected
    if urlo.absolute:
        yarl_name = urlo.name or urlo.parent.name
        assert yarl_name == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("/a/b/c", ""),
        ("https://example.com/a/b.mp4/c", ""),
        ("https://example.com/a/b.mp4/", ".mp4"),
        ("https://example.com/a/b//", ""),
        ("https://example.com/a.", ""),
        ("https://example.com/a/.mp4", ""),
        ("https://example.com/a.mp4", ".mp4"),
        ("https://example.com//a.mp4", ".mp4"),
        ("https://example.com/a/b/.mp4", ""),
        ("https://example.com/a/b/mp4.?name=d/e/f", ""),
    ],
)
def test_suffix_from_url(url: str, expected: str) -> None:
    urlo = AbsoluteHttpURL(url)
    assert urls.suffix_from_url(urlo) == expected
    if urlo.absolute:
        yarl_suffix = urlo.suffix if urlo.name else urlo.parent.suffix
        assert yarl_suffix == expected
