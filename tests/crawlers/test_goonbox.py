import pytest

from cyberdrop_dl.crawlers import goonbox
from cyberdrop_dl.url_objects import AbsoluteHttpURL


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://jpg6.su/img/960x1280-90c58bc6682426b5ff88266b8ec5a647.N3gCSXD",
            "https://jpg6.su/img/960x1280-90c58bc6682426b5ff88266b8ec5a647.N3gCSXD",
        ),
        (
            "https://simp6.jpg5.cr/images3/960x1280_90c58bc6682426b5ff88266b8ec5a647142c31c72206f9a3.jpg",
            "https://simp6.cuckcapital.cr/images3/960x1280_90c58bc6682426b5ff88266b8ec5a647142c31c72206f9a3.jpg",
        ),
        (
            "https://simp4.jpg5.su/images3/Screenshot",
            "https://simp4.cuckcapital.cr/images3/Screenshot",
        ),
        (
            "http://simp4.jpg5.su/images3/Screenshot",
            "http://simp4.cuckcapital.cr/images3/Screenshot",
        ),
        (
            "http://simp4.jpg7.cr/images3/Screenshot",
            "http://simp4.cuckcapital.cr/images3/Screenshot",
        ),
    ],
)
def test_fix_cdn(url: str, expected: str) -> None:
    result = str(goonbox._fix_cdn(AbsoluteHttpURL(url)))
    assert result == expected
