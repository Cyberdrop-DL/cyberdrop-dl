from __future__ import annotations

import dataclasses
import uuid
from typing import TYPE_CHECKING, Any, Literal, Self, TypedDict, cast

from multidict import CIMultiDict

from cyberdrop_dl.utils.dataclass import DictDataclass, deserialize, fields_names

if TYPE_CHECKING:
    from collections.abc import Mapping

    from curl_cffi.requests.impersonate import BrowserTypeLiteral
    from curl_cffi.requests.session import HttpMethod

    from cyberdrop_dl.url_objects import AbsoluteHttpURL


class RequestParams(TypedDict, total=False):
    headers: dict[str, str]
    impersonate: str | bool | None
    data: Any
    json: Any


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
        assert self.method
        assert isinstance(self.method, str)
        self.headers = prepare_headers(self.headers)
        self.impersonate = _normalize_impersonation(self.impersonate)
        if self.method == "GET" and (self.data or self.json):
            self.method = "POST"

    @classmethod
    def from_params(cls, url: AbsoluteHttpURL, method: HttpMethod, params: RequestParams) -> Self:
        return deserialize(
            cls,
            params,
            url=url,
            method=method,
            params={k: v for k, v in params.items() if k not in _REQUEST_FIELDS},
        )

    __iter__ = DictDataclass.__iter__

    def __json__(self) -> dict[str, Any]:
        me = {k: v for k, v in self if (v and k != "method") or (k in {"json", "data"} and v is not None)}
        me["url"] = str(self.url)
        if self.headers:
            me["headers"] = dict(self.headers)
        return me

    def __str__(self) -> str:
        return str(self.__json__())


_REQUEST_FIELDS = set(fields_names(Request))


def _normalize_impersonation(value: str | bool | None, /) -> BrowserTypeLiteral | Literal[False] | None:  # noqa: FBT001
    if value is True:
        return "chrome"
    if value is None:
        return None
    return cast("BrowserTypeLiteral", value) or False


def prepare_headers(headers: Mapping[str, str] | None) -> CIMultiDict[str]:
    return CIMultiDict(headers) if headers else CIMultiDict()
