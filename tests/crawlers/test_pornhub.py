import pytest
from bs4 import BeautifulSoup

from cyberdrop_dl.crawlers import pornhub

_LD_JSON = (
    '<script type="application/ld+json">{"@type": "VideoObject", "uploadDate": "2025-08-04T16:23:26+00:00"}</script>'
)
_VIDEO_DATA = "<script>window.dataLayer.push({'videodata': {'video_date_published' : '20250804'}});</script>"
_NO_DATE = "<html></html>"


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        (_LD_JSON, 1754324606),
        (_VIDEO_DATA, 1754265600),
        (_LD_JSON + _VIDEO_DATA, 1754324606),
        (_NO_DATE, None),
    ],
)
def test_extr_upload_date(html: str, expected: int | None) -> None:
    result = pornhub._extr_upload_date(BeautifulSoup(html, "html.parser"))
    assert result == expected
