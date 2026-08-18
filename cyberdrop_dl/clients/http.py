from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import http.cookies
import logging
import time
import warnings
from contextvars import ContextVar
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, Self, Unpack, final, override

import aiohttp
from aiohttp import hdrs

from cyberdrop_dl import aio, cookies, ddos_guard
from cyberdrop_dl.clients import flaresolverr, tcp, wreq
from cyberdrop_dl.clients.request import Request, RequestParams
from cyberdrop_dl.clients.response import AbstractResponse
from cyberdrop_dl.cookies import make_simple_cookie
from cyberdrop_dl.exceptions import DDOSGuardError, DownloadError
from cyberdrop_dl.signature import simple_repr
from cyberdrop_dl.utils import enter_context, truncated_preview
from cyberdrop_dl.utils.dataclass import ConfigDataclass, frozen

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable
    from pathlib import Path

    from bs4 import BeautifulSoup
    from curl_cffi.requests import AsyncSession
    from curl_cffi.requests.models import Response as CurlResponse

    from cyberdrop_dl.clients.wreq import WreqClient
    from cyberdrop_dl.config import Config
    from cyberdrop_dl.url_objects import AbsoluteHttpURL

    from . import HttpMethod


type RequestContext = contextlib.AbstractAsyncContextManager[AbstractResponse[Any]]
type RateLimit = tuple[float, float]
type JSONCheck = Callable[[Any, AbstractResponse[Any]], None]

JSON_CHECK: ContextVar[JSONCheck | None] = ContextVar("JSON_CHECK", default=None)

logger = logging.getLogger(__name__)


class _LazyResponseLog:
    def __init__(self, response: AbstractResponse[Any]) -> None:
        self.resp: AbstractResponse[Any] = response

    def __json__(self) -> dict[str, Any]:
        resp = self.resp.__json__()
        del resp["created_at"]
        if type(resp["content"]) is str:
            resp["content"] = truncated_preview(resp["content"])
        return resp

    def content(self) -> dict[str, Any]:
        return {"content": self.__json__()["content"]}

    def __str__(self) -> str:
        return str(self.__json__())

    def __repr__(self) -> str:
        return f"<{type(self).__name__}(resp={self.resp!r})>"


class RequestDoneCallback(Protocol):
    def __call__(
        self, url: AbsoluteHttpURL, response: AbstractResponse[Any], exc: Exception | None = None, /
    ) -> None: ...


@dataclasses.dataclass(slots=True, frozen=True)
class HTTPLimiter:
    global_: aio.RateLimiter
    downloads: asyncio.Semaphore
    per_domain: dict[str, aio.RateLimiter] = dataclasses.field(default_factory=dict)

    def __setitem__(self, domain: str, rate: RateLimit) -> None:
        self.per_domain[domain] = aio.RateLimiter.w_no_burst(*rate)


@final
class HTTPClient:
    request_done_callback: RequestDoneCallback | None = None

    def __init__(self, config: Config) -> None:
        self.config = config
        self.limiter = HTTPLimiter(
            aio.RateLimiter.w_no_burst(config.network.rate_limit),
            asyncio.Semaphore(config.downloads.concurrency),
        )

        self._ssl_context = None
        self._cookies: aiohttp.CookieJar | None = None
        self._flaresolverr: flaresolverr.Client | None = None
        self._curl_session: AsyncSession[CurlResponse] | None = None
        self._wreq_session: WreqClient | None = None
        self._session: aiohttp.ClientSession
        self._download_session: aiohttp.ClientSession

    __repr__ = simple_repr("config", "_ssl_context", "_cookies", "_flaresolverr", "limiter", "request_done_callback")

    @property
    def ssl_context(self):
        if self._ssl_context is None:
            self._ssl_context = self.config.network.tls.verify and tcp.create_ssl_context(
                tcp.resolve_tls_version(self.config.network.tls.min_version),
                self.config.network.tls.ca_certs,
            )
        return self._ssl_context

    @property
    def curl_session(self) -> AsyncSession[CurlResponse]:
        if self._curl_session is None:
            self._curl_session = self._create_curl_session()
        return self._curl_session

    @property
    def wreq_session(self) -> WreqClient:
        if self._wreq_session is None:
            self._wreq_session = wreq.create_client(self.config)
            jar = self._wreq_session.cookie_jar
            assert jar is not None
            for (domain, path), cookie in self.cookies.cookies.items():
                jar.add(cookie.output(), f"https://{domain}{path}")
        return self._wreq_session

    @property
    def cookies(self) -> aiohttp.CookieJar:
        # lazy cause it is loop bound for some reason
        if self._cookies is None:
            self._cookies = aiohttp.CookieJar(quote_cookie=False)
        return self._cookies

    @property
    def flaresolverr(self) -> flaresolverr.Client | None:
        if self._flaresolverr is None and (url := self.config.network.flaresolverr):
            self._flaresolverr = flaresolverr.Client(url, self._session)
        if self._flaresolverr and self._flaresolverr.is_down:
            return None
        return self._flaresolverr

    def __sync_session_cookies(self, url: AbsoluteHttpURL) -> None:
        """
        Apply to the cookies from the `curl` session into the `aiohttp` session, filtering them by the URL

        This is mostly just to get the `cf_cleareance` cookie value into the `aiohttp` session

        The reverse (sync `aiohttp` -> `curl`) is not needed at the moment, so it is skipped
        """
        now = time.time()
        for cookie in self.curl_session.cookies.jar:
            simple_cookie = make_simple_cookie(cookie, now)
            self.cookies.update_cookies(simple_cookie, url)

    def __sync_wreq_cookies(self, url: AbsoluteHttpURL) -> None:
        now = time.time()
        jar = self.wreq_session.cookie_jar
        assert jar is not None
        for cookie in jar.get_all():
            try:
                simple_cookie = wreq.make_simple_cookie(cookie, now)
            except (http.cookies.CookieError, ValueError):
                continue
            self.cookies.update_cookies(simple_cookie, url)

    async def __aenter__(self) -> Self:
        await tcp.choose_dns_resolver()
        self._session = self.create_aiohttp_session()
        self._download_session = self.create_aiohttp_session()
        return self

    async def __aexit__(self, *_: object) -> None:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._download_session.close())
            if self._curl_session is not None:
                tg.create_task(self._curl_session.close())

            if self._wreq_session is not None:
                self._wreq_session.close()

            if self._flaresolverr is not None:
                # close before closing aiohttp session
                await self._flaresolverr.aclose()
            await self._session.close()

    def _create_curl_session(self) -> AsyncSession[CurlResponse]:
        session = _create_curl_session(self.config)
        session.cookies = {cookie.key: cookie.value for cookie in self.cookies}
        return session

    def create_aiohttp_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            headers={"User-Agent": self.config.network.user_agent},
            raise_for_status=False,
            cookie_jar=self.cookies,
            timeout=aiohttp.ClientTimeout(
                total=None,
                sock_connect=self.config.network.connection_timeout,
                sock_read=self.config.network.read_timeout,
            ),
            proxy=self.config.network.proxy,
            connector=tcp.create_connector(self.ssl_context),
            requote_redirect_url=False,
        )

    async def load_cookie_files(self, cookie_files: list[Path]) -> None:
        if not cookie_files:
            return

        async for cookie in cookies.read_netscape_files(cookie_files):
            self.cookies.update_cookies(cookie)

    @contextlib.asynccontextmanager
    async def request(
        self,
        url: AbsoluteHttpURL,
        /,
        method: HttpMethod = "GET",
        **kwargs: Unpack[RequestParams],
    ) -> AsyncGenerator[AbstractResponse[Any]]:
        """Make an HTTP request and retry w flaresolverr if required"""
        async with self.raw_request(url, method, **kwargs) as resp:
            try:
                await check_http_status(resp)
            except DDOSGuardError:
                await resp.aclose()
                if not self.flaresolverr:
                    raise
                yield await self._flaresolverr_request(url, kwargs.get("data"))
            else:
                yield resp

    def raw_request(
        self,
        url: AbsoluteHttpURL,
        /,
        method: HttpMethod = "GET",
        **kwargs: Unpack[RequestParams],
    ) -> RequestContext:
        request = Request.from_params(url, method, kwargs)
        if self.config.network.impersonate:
            request.impersonate = self.config.network.impersonate

        if request.impersonate:
            request.headers.pop(hdrs.USER_AGENT, None)
        else:
            request.headers.setdefault(hdrs.USER_AGENT, self.config.network.user_agent)

        return self._request(request)

    @contextlib.asynccontextmanager
    async def _request(self, request: Request) -> AsyncGenerator[AbstractResponse[Any]]:
        logger.debug("Starting %s request [id=%s]\n%s", request.method, request.id, request)
        exc = None
        async with self.__request(request) as resp:
            resp.id = request.id
            logger.debug("Finished %s request [id=%s]\n%s", request.method, request.id, _LazyResponseLog(resp))
            try:
                yield resp
            except Exception as e:
                exc = e
                raise
            finally:
                if resp.has_content_not_logged:
                    logger.debug(
                        "Content from %s request [id=%s]\n%s",
                        request.method,
                        request.id,
                        _LazyResponseLog(resp).content(),
                    )
                if self.request_done_callback:
                    self.request_done_callback(request.url, resp, exc)
                del exc
                del resp

    @contextlib.asynccontextmanager
    async def __request(self, request: Request) -> AsyncGenerator[AbstractResponse[Any]]:
        if request.impersonate:
            if wreq.IS_INSTALLED:
                resp = await self.wreq_session.request(
                    wreq.cast_method(request.method),
                    str(request.url),
                    headers=dict(request.headers),
                    json=request.json,
                    body=request.data,
                    emulation=wreq.cast_impersonate(request.impersonate),  # pyright: ignore[reportArgumentType]
                    **request.params,
                )
                async with resp:
                    resp = AbstractResponse.create(resp)
                    self.__sync_wreq_cookies(resp.url)
                    yield resp
                    return

            async with contextlib.aclosing(
                await self.curl_session.request(
                    request.method,
                    str(request.url),
                    stream=True,
                    headers=request.headers,
                    json=request.json,
                    data=request.data,
                    impersonate=request.impersonate,
                    **request.params,
                )
            ) as curl_resp:
                self.__sync_session_cookies(request.url)
                yield AbstractResponse.create(curl_resp)

            return

        async with self._session.request(
            request.method,
            request.url,
            headers=request.headers,
            json=request.json,
            data=request.data,
            **request.params,
        ) as aio_resp:
            yield AbstractResponse.create(aio_resp)

    async def _flaresolverr_request(
        self,
        url: AbsoluteHttpURL,
        data: Any | None = None,
    ) -> AbstractResponse[Any]:
        """Make a request with FlareSolverr.

        Returns an AbstractResponse confirmed to not be a DDOS Guard page, even if flaresolverr fails to detect/solve a challenge"""

        assert self.flaresolverr
        solution = await self.flaresolverr.request(url, data)
        self.cookies.update_cookies(solution.cookies)
        flaresolverr.verify_solution(self.config.network.user_agent, solution)
        return AbstractResponse.create(solution)

    @contextlib.asynccontextmanager
    async def rate_limit_ctx(self, domain: str, json_check: JSONCheck | None = None) -> AsyncGenerator[None]:
        limiter = self.limiter.per_domain.get(domain, contextlib.nullcontext())
        with enter_context(JSON_CHECK, json_check):
            async with limiter, self.limiter.global_:
                yield


async def _check_json(response: AbstractResponse[Any]) -> None:
    if "json" not in response.content_type:
        return

    try:
        data = await response.json()
    except Exception:
        logger.exception("Unable to decode JSON response from %s", response.url)
        return

    if check := JSON_CHECK.get():
        check(data, response)
        return


class HTTPController(Protocol):
    __http_config__: ClassVar[HTTPConfig]
    __http_ctx__: HTTPContext
    client: HTTPClient


class HTTPMixin(HTTPController, Protocol):
    @contextlib.asynccontextmanager
    async def request(
        self,
        url: AbsoluteHttpURL,
        /,
        method: HttpMethod = "GET",
        **kwargs: Unpack[RequestParams],
    ) -> AsyncGenerator[AbstractResponse[Any]]:

        ctx = self.__http_ctx__
        if ctx.throttle is not None:
            await ctx.throttle()

        kwargs.setdefault("impersonate", ctx.impersonate)
        kwargs["headers"] = ctx.headers | kwargs.setdefault("headers", {})

        async with (
            self.client.rate_limit_ctx(ctx.domain, ctx.json_check),
            self.client.request(url, method, **kwargs) as resp,
        ):
            yield resp

    async def request_json(
        self,
        url: AbsoluteHttpURL,
        /,
        method: HttpMethod = "GET",
        **kwargs: Unpack[RequestParams],
    ) -> Any:
        async with self.request(url, method, **kwargs) as resp:
            return await resp.json()

    async def request_soup(
        self,
        url: AbsoluteHttpURL,
        /,
        method: HttpMethod = "GET",
        **kwargs: Unpack[RequestParams],
    ) -> BeautifulSoup:
        async with self.request(url, method, **kwargs) as resp:
            return await resp.soup()

    async def request_text(
        self,
        url: AbsoluteHttpURL,
        /,
        method: HttpMethod = "GET",
        **kwargs: Unpack[RequestParams],
    ) -> str:
        async with self.request(url, method, **kwargs) as resp:
            return await resp.text()

    async def request_location(
        self,
        url: AbsoluteHttpURL,
        /,
        method: HttpMethod = "HEAD",
        **kwargs: Unpack[RequestParams],
    ) -> AbsoluteHttpURL | None:
        async with self.request(url, method, **kwargs) as resp:
            return resp.location

    async def request_redirect(
        self,
        url: AbsoluteHttpURL,
        /,
        method: HttpMethod = "GET",
        **kwargs: Unpack[RequestParams],
    ) -> AbsoluteHttpURL:
        "Like request_location, but it uses a GET request instead of HEAD to follow all redirects upto the final destination"
        async with self.request(url, method, **kwargs) as resp:
            return resp.url


@final
class HTTPControllerProxy[T: HTTPMixin]:
    def __init__(self, http: T) -> None:
        self.controller = http
        self.__call__ = http.request
        self.json = http.request_json
        self.soup = http.request_soup
        self.text = http.request_text
        self.redirect = http.request_redirect
        self.location = http.request_location


def _create_curl_session(config: Config) -> AsyncSession[CurlResponse]:
    from curl_cffi.aio import AsyncCurl
    from curl_cffi.requests import AsyncSession
    from curl_cffi.utils import CurlCffiWarning

    loop = asyncio.get_running_loop()

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=CurlCffiWarning)
        acurl = AsyncCurl(loop=loop)

    return AsyncSession(
        loop=loop,
        async_curl=acurl,
        impersonate="chrome",
        verify=config.network.tls.verify,
        proxy=str(proxy) if (proxy := config.network.proxy) else None,
        timeout=config.network.curl_timeout,
        max_redirects=8,
    )


@final
@frozen
class HTTPConfig(ConfigDataclass):
    __attr_name__: ClassVar[str] = "__http_config__"
    headers: dict[str, str] | None = None
    impersonate: str | bool | None = None
    rate_limit: RateLimit | None = None
    json_check: JSONCheck | None = None

    @classmethod
    def default_headers(
        cls,
        user_agent: str | None = None,
        referer: str | None = None,
        host: str | None = None,
        content_type: str | None = None,
        accept: str | None = None,
        **kwargs: str,
    ) -> HTTPConfig:
        headers = {
            hdrs.USER_AGENT: user_agent,
            hdrs.REFERER: referer,
            hdrs.HOST: host,
            hdrs.CONTENT_TYPE: content_type,
            hdrs.ACCEPT: accept,
        } | kwargs
        return HTTPConfig(headers={k: v for k, v in headers.items() if v is not None})

    @override
    def __or__(self, other: Self) -> Self:  # pyright: ignore[reportIncompatibleMethodOverride]
        changes = other._changes()

        if self.headers and other.headers:
            changes["headers"] = self.headers | other.headers

        elif (headers := (self.headers or other.headers)) is not None:
            changes["headers"] = headers.copy()

        return dataclasses.replace(self, **changes)


@final
@dataclasses.dataclass(slots=True, frozen=True)
class HTTPContext:
    domain: str
    rate_limit: RateLimit
    json_check: JSONCheck | None = None
    impersonate: str | bool | None = None
    throttle: Callable[[], Awaitable[Any]] | None = None
    headers: dict[str, str] = dataclasses.field(default_factory=dict)

    @classmethod
    def build(
        cls,
        domain: str,
        config: HTTPConfig,
        throttle: Callable[[], Awaitable[Any]] | None = None,
    ) -> HTTPContext:
        assert config.rate_limit is not None

        return cls(
            domain=domain,
            rate_limit=config.rate_limit,
            headers=config.headers or {},
            impersonate=config.impersonate,
            json_check=config.json_check,
            throttle=throttle,
        )


async def check_http_status(response: AbstractResponse[Any]) -> None:
    if HTTPStatus.OK <= response.status < HTTPStatus.BAD_REQUEST:
        # Check DDosGuard even on successful pages
        await ddos_guard.check_resp(response)
        return

    await _check_json(response)
    await ddos_guard.check_resp(response)
    raise DownloadError(response.status)
