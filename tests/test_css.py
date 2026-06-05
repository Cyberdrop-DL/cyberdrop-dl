import pytest

from cyberdrop_dl.utils import css


@pytest.mark.parametrize(
    ("raw", "domain", "expected"),
    [
        ("cyberdrop-dl | GitHub", "github.com", "cyberdrop-dl"),
        ("cyberdrop-dl - GitHub", "github.com", "cyberdrop-dl"),
        ("cyberdrop-dl | GitHub - Bar", "github.com", "cyberdrop-dl"),
        ("", "github.com", ""),
        ("   ", "github.com", "   "),
        # case-insensitive
        ("cyberdrop-dl | GITHUB", "GitHub.com", "cyberdrop-dl"),
        ("cyberdrop-dl - GiThUb", "GITHUB.io", "cyberdrop-dl"),
        # sub-domains
        ("News | www.github.co", "www.github.co.uk", "News"),
        # no match -> unchanged
        ("cyberdrop-dl | Foo", "github.com", "cyberdrop-dl | Foo"),
        ("cyberdrop-dl - Foo", "github.com", "cyberdrop-dl - Foo"),
        # clean up once
        ("cyberdrop-dl | Foo - GitHub", "github.com", "cyberdrop-dl | Foo"),
        ("A | B | GitHub", "github.com", "A | B"),
        ("A - B - GitHub", "github.com", "A - B"),
    ],
)
def test_rstrip_domain(raw: str, domain: str, expected: str) -> None:
    assert css.rstrip_domain(raw, domain) == expected


def test_no_domain_raise_error() -> None:
    with pytest.raises(AssertionError):
        css.rstrip_domain("cyberdrop-dl | Foo", "")
