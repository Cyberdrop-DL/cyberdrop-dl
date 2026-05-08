import datetime
from pathlib import Path

import pytest

from cyberdrop_dl import csv_logs
from cyberdrop_dl.url_objects import AbsoluteHttpURL

now = datetime.datetime(2026, 5, 8)


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://static.scdn.st/e2f8a4c6-3d7b-4e19-9a5c-8b1d6f0e3a7c/thumbs/f7e8625e-b50b-42c3-93da-d74bce716c41-md8f1c79417cd16004-zU4LIum1.png",
            "/https-static.scdn.st-e2f8a4c6-3d7b-4e19-9a5c-8b1d6f0e3a7c-thumbs-f7e8625e-b50b-42c3-93da-d74bce716c41-md8f1c79417cd16004-zU4LIum1.png_20260508_000000.html",
        ),
        (
            "https://cloud.mail.ru/public/d1LR/hMBXG2mFo",
            "/https-cloud.mail.ru-public-d1LR-hMBXG2mFo_20260508_000000.html",
        ),
        (
            "https://www.tokyomotion.net/video/5884366/%E3%83%A1%E3%82%B9%E7%89%9B%E3%81%8A%E3%81%BB%E3%82%A4%E3%82%AD%E3%83%81%E3%82%AF%E3%83%8B%E3%83%BC",
            "/https-www.tokyomotion.net-video-5884366-%E3%83%A1%E3%82%B9%E7%89%9B%E3%81%8A%E3%81%BB%E3%82%A4%E3%82%AD%E3%83%81%E3%82%AF%E3%83%8B%E3%83%BC_20260508_000000.html",
        ),
    ],
)
def test_prepare_resp_filename(url: str, expected: str) -> None:
    result = csv_logs._prepare_resp_file(Path("/"), AbsoluteHttpURL(url), now)
    assert result.as_posix().count("/") == 1
    assert result.as_posix() == expected
