from __future__ import annotations

import dataclasses
from types import MappingProxyType
from typing import TYPE_CHECKING

import aiohttp.multipart
from aiohttp import hdrs

from cyberdrop_dl.exceptions import ScrapeError

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclasses.dataclass(slots=True, frozen=True)
class ContentDisposition:
    type: str | None
    parameters: MappingProxyType[str, str]
    filename: str | None


def get_content_disposition(headers: Mapping[str, str]) -> ContentDisposition | None:
    try:
        header = headers[hdrs.CONTENT_DISPOSITION]
    except KeyError:
        return None
    else:
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
