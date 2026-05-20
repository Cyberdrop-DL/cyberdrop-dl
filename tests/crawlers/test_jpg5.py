import pytest

from cyberdrop_dl.crawlers import jpg5
from cyberdrop_dl.url_objects import AbsoluteHttpURL


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "MWIxMTE4MDQxYTU2NDA1OTE2MWExZTE5NWI1ZTAwMWMxNzEyMjMxMjE5MDQwNDAyMDU1YTFhMWE0ZTFkMDgxMjE0MDYwMTUyNWY1YzQ0NDMwYjU0NWU0YzU5MzM1NjQ2MDY0NjRiMGIwZTQ2NTU1MTQ2NGQ3MjQ1MGI1ODE2MDU1MTRjNGI1ZTU3MTY1ZDE2MTA1NjEzNTc0NDUyNDM0NzQxMDY1ZjQ1MGE1YjVkNDQ1NTQ1MTU1MDBjNDM0ZDAzMDQxZQ==",
            "https://simp6.cuckcapital.cr/images3/960x1280_90c58bc6682426b5ff88266b8ec5a647142c31c72206f9a3.jpg",
        ),
        (
            "MWIxMTE4MDQxYTU2NDA1OTE2MWExZTE5NWI1ZTAwMWMxNzEyMjMxMjE5MDQwNDAyMDU1YTFhMWE0ZTFkMDgxMjE0MDYwMTUyNWYxNzE3MTExNjA2MGQ1OTE5MDUwMTFkNDgwMzFhMGE1ZDQwNTIwZjQ1MWM3MDE2NWE1ZDQxMDcwZDQwMWQ1ZDU3MTIwNzVkMTkxMzE1",
            "https://simp6.cuckcapital.cr/images3/rebeca-pink-pic001f1e0e301dd4d56fb.jpg",
        ),
        (
            "http://simp4.jpg5.su/images3/Screenshot",
            "http://simp4.jpg5.su/images3/Screenshot",
        ),
    ],
)
def test_decode_url(url: str, expected: str) -> None:
    result = str(jpg5._decode_url(url))
    assert result == expected


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
    ],
)
def test_fix_cdn(url: str, expected: str) -> None:
    result = str(jpg5._fix_cdn(AbsoluteHttpURL(url)))
    assert result == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "MWIxMTE4MDQxYTU2NDA1OTE2MWExZTE5NWI1ZTAwMWMxNzEyMjMxMjE5MDQwNDAyMDU1YTFhMWE0ZTFkMDgxMjE0MDYwMTUyNWY1YzQ0NDMwYjU0NWU0YzU5MzM1NjQ2MDY0NjRiMGIwZTQ2NTU1MTQ2NGQ3MjQ1MGI1ODE2MDU1MTRjNGI1ZTU3MTY1ZDE2MTA1NjEzNTc0NDUyNDM0NzQxMDY1ZjQ1MGE1YjVkNDQ1NTQ1MTU1MDBjNDM0ZDAzMDQxZQ==",
            "https://simp6.cuckcapital.cr/images3/960x1280_90c58bc6682426b5ff88266b8ec5a647142c31c72206f9a3.jpg",
        ),
        (
            "MWIxMTE4MDQxYTU2NDA1OTE2MWExZTE5NWI1ZTAwMWMxNzEyMjMxMjE5MDQwNDAyMDU1YTFhMWE0ZTFkMDgxMjE0MDYwMTUyNWYxNzE3MTExNjA2MGQ1OTE5MDUwMTFkNDgwMzFhMGE1ZDQwNTIwZjQ1MWM3MDE2NWE1ZDQxMDcwZDQwMWQ1ZDU3MTIwNzVkMTkxMzE1",
            "https://simp6.cuckcapital.cr/images3/rebeca-pink-pic001f1e0e301dd4d56fb.jpg",
        ),
        (
            "http://simp4.jpg5.su/images3/Screenshot",
            "http://simp4.cuckcapital.cr/images3/Screenshot",
        ),
        (
            "https://jpg6.su/img/Nv7ZaLE",
            "https://jpg6.su/img/Nv7ZaLE",
        ),
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
    ],
)
def test_parse_url(url: str, expected: str) -> None:
    result = str(jpg5.JPG5Crawler.parse_url(url))
    assert result == expected
