from __future__ import annotations

import dataclasses
import uuid
from typing import TYPE_CHECKING, Any, Literal, cast

from multidict import CIMultiDict

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping

    from curl_cffi.requests.impersonate import BrowserTypeLiteral
    from curl_cffi.requests.session import HttpMethod

    from cyberdrop_dl.url_objects import AbsoluteHttpURL


@dataclasses.dataclass(slots=True, kw_only=True)
class Request:
    url: AbsoluteHttpURL
    method: HttpMethod = "GET"
    headers: CIMultiDict[str] = dataclasses.field(default_factory=CIMultiDict)
    impersonate: BrowserTypeLiteral | Literal[False] | None = None
    data: Any = None
    json: Any = None
    params: dict[str, Any] = dataclasses.field(default_factory=dict)

    id: str = dataclasses.field(init=False, default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if self.method == "GET" and (self.data or self.json):
            self.method = "POST"

    def __json__(self) -> dict[str, Any]:
        return dict(self._serialize())

    def _serialize(self) -> Generator[tuple[str, Any]]:
        yield "url", str(self.url)
        if self.headers:
            yield "headers", dict(self.headers)
        if self.impersonate is not None:
            yield "impersonate", self.impersonate
        if self.data is not None:
            yield "data", self.data
        if self.json is not None:
            yield "json", self.json

    def __str__(self) -> str:
        return str(self.__json__())


def normalize_impersonation(value: str | bool | None, /) -> BrowserTypeLiteral | Literal[False] | None:
    if value is True:
        return "chrome"
    if value is None:
        return None
    return cast("BrowserTypeLiteral", value) or False


def prepare_headers(headers: Mapping[str, str] | None) -> CIMultiDict[str]:
    return CIMultiDict(headers) if headers else CIMultiDict()
