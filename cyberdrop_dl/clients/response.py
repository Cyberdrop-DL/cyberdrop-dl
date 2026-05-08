from __future__ import annotations

import asyncio
import dataclasses
import datetime
import json
from abc import ABC, abstractmethod
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Generic, Literal, Self, final

import aiohttp.multipart
from aiohttp import ClientResponse, hdrs
from bs4 import BeautifulSoup
from multidict import CIMultiDict, CIMultiDictProxy
from propcache import under_cached_property
from typing_extensions import TypeVar, override

from cyberdrop_dl.clients.flaresolverr import Solution as FlaresolverrSolution
from cyberdrop_dl.exceptions import InvalidContentTypeError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import parse_url

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from curl_cffi.requests.models import Response as CurlResponse


else:

    class CurlResponse: ...


_ResponseT = TypeVar(
    "_ResponseT",
    bound=ClientResponse | CurlResponse | FlaresolverrSolution,
    infer_variance=True,
    default=Any,
)


@dataclasses.dataclass(slots=True, frozen=True)
class ContentDisposition:
    type: str | None
    parameters: MappingProxyType[str, str]
    raw_filename: str | None

    @property
    def filename(self) -> str:
        if name := self.raw_filename:
            return name

        msg = "Content disposition has no filename information"
        raise ScrapeError(422, msg)


@dataclasses.dataclass(slots=True)
class AbstractResponse(ABC, Generic[_ResponseT]):
    """
    Class to represent common methods and attributes between:
        - `aiohttp.ClientResponse`
        - `curl_cffi.Response`
        - `FlareSolverrSolution`
    """

    content_type: str
    status: int
    headers: CIMultiDictProxy[str]
    url: AbsoluteHttpURL
    location: AbsoluteHttpURL | None

    _resp: _ResponseT
    _text: str = ""
    _cache: dict[str, Any] = dataclasses.field(init=False, compare=False, default_factory=dict)
    _lock: asyncio.Lock = dataclasses.field(init=False, compare=False, default_factory=asyncio.Lock)
    created_at: datetime.datetime = dataclasses.field(
        init=False,
        compare=False,
        default_factory=lambda: datetime.datetime.now(datetime.UTC).replace(microsecond=0),
    )

    def __repr__(self) -> str:
        return f"<{type(self).__name__} [{self.status}] ({self.url})>"

    def __json__(self) -> dict[str, Any]:
        if content := self._text:
            if "json" in self.content_type:
                content = json.loads(content)

            elif "html" in self.content_type:
                content = BeautifulSoup(content, "html.parser").prettify(formatter="html")

        elif not ("json" in self.content_type or "html" in self.content_type):
            content = f"<{self.content_type} payload>"

        return {
            "url": str(self.url),
            "status_code": self.status,
            "created_at": str(self.created_at),
            "response_headers": dict(self.headers),
            "content": content,
        }

    @abstractmethod
    async def _read(self) -> bytes: ...

    @abstractmethod
    async def _read_text(self, encoding: str | None = None) -> str: ...

    @abstractmethod
    def iter_chunked(self, size: int) -> AsyncIterator[bytes]: ...

    @abstractmethod
    async def aclose(self) -> None: ...

    @classmethod
    def create(cls, resp: _ResponseT, /) -> _AIOHTTPResponse | _FlareSolverrResponse | _CurlResponse:
        if isinstance(resp, ClientResponse):
            return _AIOHTTPResponse.create(resp)

        if isinstance(resp, FlaresolverrSolution):
            return _FlareSolverrResponse.create(resp)

        return _CurlResponse.create(resp)

    @final
    @under_cached_property
    def content_disposition(self) -> ContentDisposition:
        try:
            header = self.headers[hdrs.CONTENT_DISPOSITION]
        except KeyError:
            msg = f"No content disposition header found in response from {self.url}"
            raise ScrapeError(422, msg) from None

        disposition_type, params = aiohttp.multipart.parse_content_disposition(header)
        params = MappingProxyType(params)
        filename = aiohttp.multipart.content_disposition_filename(params)
        return ContentDisposition(disposition_type, params, filename)

    @final
    @property
    def aiohttp_resp(self) -> ClientResponse:
        if type(self._resp) is ClientResponse:
            return self._resp
        raise RuntimeError(f"Unexpected response type: {type(self._resp)!r}")

    @property
    def ok(self) -> bool:
        """Returns `True` if `status` is less than `400`, `False` if not.

        This is **not** a check for ``200 OK``
        """
        return self.status < 400

    @final
    async def read(self) -> bytes:
        async with self._lock:
            return await self._read()

    @final
    async def text(self, encoding: str | None = None) -> str:
        if self._text:
            return self._text

        async with self._lock:
            if not self._text:
                self._text = await self._read_text(encoding)
            return self._text

    @final
    async def soup(self, encoding: str | None = None) -> BeautifulSoup:
        self.__check_content_type("text", "html", expecting="HTML")
        if content := await self.text(encoding):
            return BeautifulSoup(content, "html.parser")

        raise ScrapeError(204, "Received empty HTML response")

    @final
    async def json(
        self,
        encoding: str | None = None,
        content_type: tuple[str, ...] | str | Literal[False] | None = ("text/plain", "json"),
    ) -> Any:
        if self.status == 204:
            raise ScrapeError(204)

        if content_type:
            if isinstance(content_type, str):
                content_type = (content_type,)

            self.__check_content_type(*content_type, expecting="JSON")

        return json.loads(await self.text(encoding))

    @final
    def create_report(self, exc: Exception | None = None, **extras: Any) -> str:

        me = self.__json__()
        if exc:
            me |= {"error": str(exc), "exception": repr(exc)}

        if extras:
            me |= extras

        if "json" in self.content_type:
            return json.dumps(me, indent=2, ensure_ascii=False)

        body: str = me.pop("content")
        resp_info = json.dumps(me, indent=2, ensure_ascii=False)
        return f"<!-- cyberdrop-dl request response \n{resp_info}\n-->\n{body}"

    def __check_content_type(self, content_type: str, *additional_content_types: str, expecting: str) -> None:
        if not any(type_ in self.content_type for type_ in (content_type, *additional_content_types)):
            msg = f"Received {self.content_type}, was expecting {expecting}"
            raise InvalidContentTypeError(message=msg)


class _FlareSolverrResponse(AbstractResponse[FlaresolverrSolution]):
    __slots__ = ()

    async def _read(self) -> bytes:
        return self._text.encode()

    async def _read_text(self, encoding: str | None = None) -> str:
        return self._text

    async def iter_chunked(self, size: int) -> AsyncIterator[bytes]:
        yield self._text.encode()

    async def aclose(self) -> None: ...

    @override
    @classmethod
    def create(cls, solution: FlaresolverrSolution, /) -> Self:
        content_type, location = _parse_headers(solution.url, solution.headers)
        if not content_type:
            content_type = _infer_content_type_from_body(solution.content)

        return cls(
            content_type=content_type,
            status=solution.status,
            headers=solution.headers,
            url=solution.url,
            location=location,
            _text=solution.content,
            _resp=solution,
        )


class _AIOHTTPResponse(AbstractResponse[ClientResponse]):
    __slots__ = ()

    async def _read(self) -> bytes:
        return await self._resp.read()

    async def _read_text(self, encoding: str | None = None) -> str:
        return await self._resp.text(encoding)

    def iter_chunked(self, size: int) -> AsyncIterator[bytes]:
        return self._resp.content.iter_chunked(size)

    async def aclose(self) -> None:
        self._resp.release()
        await self._resp.wait_for_close()

    @override
    @classmethod
    def create(cls, resp: ClientResponse, /) -> Self:
        url = AbsoluteHttpURL(resp.url)
        content_type, location = _parse_headers(url, resp.headers)
        return cls(
            content_type=content_type,
            status=resp.status,
            headers=resp.headers,
            url=url,
            location=location,
            _text="",
            _resp=resp,
        )


class _CurlResponse(AbstractResponse[CurlResponse]):
    __slots__ = ()

    async def _read(self) -> bytes:
        return await self._resp.acontent()

    async def _read_text(self, encoding: str | None = None) -> str:
        if encoding:
            self._resp.encoding = encoding
        return await self._resp.atext()

    def iter_chunked(self, size: int) -> AsyncIterator[bytes]:
        # Curl does not support size. We get chunks as they come
        return self._resp.aiter_content()

    async def aclose(self) -> None:
        await self._resp.aclose()

    @override
    @classmethod
    def create(cls, resp: CurlResponse, /) -> Self:
        headers = CIMultiDictProxy(
            CIMultiDict(((name, value) for name, value in resp.headers.multi_items() if value is not None))
        )
        url = AbsoluteHttpURL(resp.url, encoded="%" in resp.url)
        content_type, location = _parse_headers(url, headers)
        return cls(
            content_type=content_type,
            status=resp.status_code,
            headers=headers,
            url=url,
            location=location,
            _text="",
            _resp=resp,
        )


def _parse_headers(url: AbsoluteHttpURL, headers: CIMultiDictProxy[str]) -> tuple[str, AbsoluteHttpURL | None]:
    if location := headers.get(hdrs.LOCATION):
        location = parse_url(location, url.origin(), trim=False)
    else:
        location = None

    content_type = (headers.get(hdrs.CONTENT_TYPE) or "").lower()
    return content_type, location


def _infer_content_type_from_body(content: str) -> str:
    text = content.lstrip()
    if text.startswith("<") and "html>" in text[:20]:
        return "text/html"
    if text.startswith(("{", "[")):
        return "application/json"
    return ""
