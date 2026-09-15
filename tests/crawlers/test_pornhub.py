import pytest
from bs4 import BeautifulSoup

from cyberdrop_dl.crawlers import pornhub
from cyberdrop_dl.utils import css

_LD_JSON = (
    '<script type="application/ld+json">{"@type": "VideoObject", "uploadDate": "2025-08-04T16:23:26+00:00"}</script>'
)
_UNLISTED = '<span class="notifMessage">This video is unlisted. Only those with a link can see it.</span>'


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        (_LD_JSON, 1754324606),
        (_UNLISTED, None),
        (_LD_JSON + _UNLISTED, 1754324606),
    ],
)
def test_extr_upload_date(html: str, expected: int | None) -> None:
    result = pornhub._extr_upload_date(BeautifulSoup(html, "html.parser"), html)
    assert result == expected


def test_extr_upload_date_missing_ld_json_raises() -> None:
    html = "<html></html>"
    with pytest.raises(css.SelectorError):
        pornhub._extr_upload_date(BeautifulSoup(html, "html.parser"), html)
