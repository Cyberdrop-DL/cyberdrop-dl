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
    value: str
    msg: str | None = None
    error: int | str = HTTPStatus.NOT_FOUND

    def __post_init__(self) -> None:
        value = self.value.strip('"')
        if value.startswith("W/"):
            raise ValueError("Weak entity tags are not allowed")

        object.__setattr__(self, "value", value)


def check(headers: Mapping[str, str]) -> None:
    e_tag_value = headers.get("ETag", "").strip('"')
    if e_tag := _ETAGS.get(e_tag_value):
        raise DownloadError(e_tag.error, e_tag.msg)


def register(*etags: ETag) -> None:
    for new_etag in etags:
        if old_tag := _ETAGS.get(new_etag.value):
            raise RuntimeError(f"Duplicated entity tag: {old_tag = }, {new_etag = }")

        _ETAGS[new_etag.value] = new_etag
