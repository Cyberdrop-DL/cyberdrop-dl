from __future__ import annotations

import dataclasses
from http import HTTPStatus
from typing import TYPE_CHECKING

from cyberdrop_dl.exceptions import DownloadError

if TYPE_CHECKING:
    from collections.abc import Mapping

_ETAGS: dict[str, ETag] = {}


@dataclasses.dataclass(slots=True, frozen=True)
class ETag:
    domain: str
    value: str
    msg: str | None = None
    error: int | str = HTTPStatus.NOT_FOUND


for domain, params in {
    "Imgur": [("d835884373f4d6c8f24742ceabe74946", "Image has been removed")],
    "SimpCity": [("65b7753c-528a", "SC Scrape Image")],
    "PixHost": [("5c4fb843-ece", "PixHost Removed Image")],
    "eFukt": [
        ("637be5da-11d2b", "Video removed"),
        ("63a05f27-11d2b", "Video removed"),
        ("5a56b09d-1485eb", "Video removed"),
    ],
    "ImageVenue": [
        ("19fdf2cd6-383c-5a4cd5b6710ed", "Image not found"),
        ("383c-5a4cd5b6710ed", "Image not found"),
    ],
}.items():
    for param in params:
        new_etag = ETag(domain, *param)
        if old_tag := _ETAGS.get(new_etag.value):
            raise RuntimeError(f"Duplicated etag: {old_tag = }, {new_etag = }")
        _ETAGS[new_etag.value] = new_etag


def check(headers: Mapping[str, str]) -> None:
    e_tag_value = headers.get("ETag", "").strip('"')
    if e_tag := _ETAGS.get(e_tag_value):
        raise DownloadError(e_tag.error, e_tag.msg)
