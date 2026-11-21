from __future__ import annotations

import dataclasses
from http import HTTPStatus
from types import MappingProxyType
from typing import TYPE_CHECKING

import aiohttp.multipart
from aiohttp import hdrs

from cyberdrop_dl.exceptions import DownloadError, ScrapeError
from cyberdrop_dl.utils import dates

if TYPE_CHECKING:
    from collections.abc import Mapping

_CONTENT_TYPES_OVERRIDES: Mapping[str, str] = {"text/vnd.trolltech.linguist": "video/MP2T"}


@dataclasses.dataclass(slots=True, frozen=True)
class ContentDisposition:
    type: str | None
    parameters: Mapping[str, str]
    filename: str | None


def get_content_disposition(headers: Mapping[str, str]) -> ContentDisposition | None:
    if header := headers.get(hdrs.CONTENT_DISPOSITION):
        return parse_content_disposition(header)


def get_content_disposition_filename(headers: Mapping[str, str]) -> str | None:
    if cd := get_content_disposition(headers):
        return cd.filename


def content_disposition(headers: Mapping[str, str]) -> ContentDisposition:
    if cd := get_content_disposition(headers):
        return cd

    raise ScrapeError(422, "No content disposition header found")


def content_disposition_filename(headers: Mapping[str, str]) -> str:
    cd = content_disposition(headers)
    if cd.filename:
        return cd.filename

    raise ScrapeError(422, "Content disposition has no filename information")


def parse_content_disposition(header: str, name: str = "filename") -> ContentDisposition:
    disposition_type, params = aiohttp.multipart.parse_content_disposition(header)
    params = MappingProxyType(params)
    filename = aiohttp.multipart.content_disposition_filename(params, name)
    return ContentDisposition(disposition_type, params, filename or None)


def content_length(headers: Mapping[str, str], *, _required: bool = False) -> int:
    try:
        return int(headers[hdrs.CONTENT_LENGTH])
    except KeyError:
        if not _required:
            return 0
        msg = f"Download response has no `{hdrs.CONTENT_LENGTH}` header. Refusing to download"
        raise DownloadError(HTTPStatus.LENGTH_REQUIRED, msg, retry=False) from None


def get_last_modified(headers: Mapping[str, str]) -> int | None:
    if date_str := headers.get(hdrs.LAST_MODIFIED):
        return int(dates.parse_http(date_str).timestamp())


def get_content_type(headers: Mapping[str, str]) -> str | None:
    content_type = headers.get(hdrs.CONTENT_TYPE)
    if not content_type:
        return None

    override_key = next((name for name in _CONTENT_TYPES_OVERRIDES if name in content_type), "<NO_OVERRIDE>")
    return _CONTENT_TYPES_OVERRIDES.get(override_key) or content_type
