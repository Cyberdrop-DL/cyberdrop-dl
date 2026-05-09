from __future__ import annotations

from http import HTTPStatus

import pytest
from multidict import CIMultiDict

from cyberdrop_dl.clients.etag import check
from cyberdrop_dl.exceptions import DownloadError


def test_missing_etag_header() -> None:
    check({})
    check({"Content-Type": "text/plain"})


def test_unknown_etag() -> None:
    check({"ETag": '"unknown-value"'})


def test_known_etag() -> None:
    value = "d835884373f4d6c8f24742ceabe74946"
    with pytest.raises(DownloadError) as exc_info:
        check({"ETag": f"{value}"})
    assert exc_info.value.status == HTTPStatus.NOT_FOUND
    assert exc_info.value.message == "Image has been removed"


def test_etag_with_quotes() -> None:
    value = "65b7753c-528a"
    with pytest.raises(DownloadError):
        check({"ETag": f'"{value}"'})


def test_case_insensitive_header_lookup() -> None:
    value = "5c4fb843-ece"
    headers = {"etag": f'"{value}"'}
    check(headers)

    with pytest.raises(DownloadError):
        check(CIMultiDict(headers))
