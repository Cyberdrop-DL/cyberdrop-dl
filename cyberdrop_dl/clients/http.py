from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import time
import warnings
from abc import ABC, abstractmethod
from contextvars import ContextVar
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Literal, Protocol, Self, cast, final

import aiohttp
from curl_cffi.aio import AsyncCurl
from curl_cffi.requests import AsyncSession
from curl_cffi.utils import CurlCffiWarning

from cyberdrop_dl import aio, cookies, ddos_guard, signature
from cyberdrop_dl.clients import flaresolverr, tcp
from cyberdrop_dl.clients.request import Request, normalize_impersonation, prepare_headers
from cyberdrop_dl.clients.response import AbstractResponse
from cyberdrop_dl.cookies import make_simple_cookie
from cyberdrop_dl.exceptions import DDOSGuardError, DownloadError
from cyberdrop_dl.utils import truncated_preview

if TYPE_CHECKING:
    import ssl
    from collections.abc import AsyncGenerator, Callable, Mapping
    from pathlib import Path

    from bs4 import BeautifulSoup
    from curl_cffi.requests.models import Response as CurlResponse
    from curl_cffi.requests.session import HttpMethod

    from cyberdrop_dl.config import Config
    from cyberdrop_dl.manager import Manager
    from cyberdrop_dl.url_objects import AbsoluteHttpURL

_JSON_CHECK: ContextVar[Callable[[Any, AbstractResponse[Any]], None] | None] = ContextVar("_JSON_CHECK", default=None)

logger = logging.getLogger(__name__)


class _LazyResponseLog:
    def __init__(self, response: AbstractResponse[Any]) -> None:
        self.response: AbstractResponse[Any] = response

    def __json__(self) -> dict[str, Any]:
        resp = self.response.__json__()
        del resp["created_at"]
        if type(resp["content"]) is str:
            resp["content"] = truncated_preview(resp["content"])
        return resp

    def __str__(self) -> str:
        return str(self.__json__())


class RequestDoneCallback(Protocol):
    def __call__(
        self, url: AbsoluteHttpURL, response: AbstractResponse[Any], exc: Exception | None = None, /
    ) -> None: ...


@final
@dataclasses.dataclass(slots=True)
class HTTPClient:
    config: Config
    impersonate: (
        Literal[
            "chrome",
            "edge",
            "safari",
            "safari_ios",
            "chrome_android",
            "firefox",
        ]
        | None
    ) = None
    request_done_callback: RequestDoneCallback | None = None

    rate_limits: dict[str, aio.RateLimiter] = dataclasses.field(init=False, default_factory=dict)
    global_rate_limiter: aio.RateLimiter = dataclasses.field(init=False)
    global_download_limiter: asyncio.Semaphore = dataclasses.field(init=False)

    _ssl_context: ssl.SSLContext | Literal[False] = dataclasses.field(init=False)
    _cookies: aiohttp.CookieJar | None = dataclasses.field(init=False, default=None)
    _flaresolverr: flaresolverr.Client | None = dataclasses.field(init=False, default=None)
    _curl_session: AsyncSession[CurlResponse] | None = dataclasses.field(init=False, default=None)
    _session: aiohttp.ClientSession = dataclasses.field(init=False)
    _download_session: aiohttp.ClientSession = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self._ssl_context = tcp.create_ssl_context(self.config.global_settings.general.ssl_context)
        self.global_rate_limiter = aio.RateLimiter.w_no_burst(
            self.config.global_settings.rate_limiting_options.rate_limit
        )
        self.global_download_limiter = asyncio.Semaphore(
            self.config.global_settings.rate_limiting_options.max_simultaneous_downloads
        )

    @staticmethod
    def from_manager(manager: Manager) -> HTTPClient:
        client = HTTPClient(config=manager.config, impersonate=manager.cli_args.impersonate)
        if manager.config.settings.files.save_pages_html or manager.config.settings.files.dump_responses:
            client.request_done_callback = manager.logs.write_response

        return client

    @property
    def curl_session(self) -> AsyncSession[CurlResponse]:
        if self._curl_session is None:
            self._curl_session = self._create_curl_session()
        return self._curl_session

    @property
    def cookies(self) -> aiohttp.CookieJar:
        # lazy cause it is loop bound for some reason
        if self._cookies is None:
            self._cookies = aiohttp.CookieJar(quote_cookie=False)
        return self._cookies

    @property
    def flaresolverr(self) -> flaresolverr.Client | None:
        if self._flaresolverr is None and (url := self.config.global_settings.general.flaresolverr):
            self._flaresolverr = flaresolverr.Client(url, self._session)
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
            headers={"User-Agent": self.config.global_settings.general.user_agent},
            raise_for_status=False,
            cookie_jar=self.cookies,
            timeout=self.config.global_settings.rate_limiting_options.aiohttp_timeout,
            proxy=self.config.global_settings.general.proxy,
            connector=tcp.create_connector(self._ssl_context),
            requote_redirect_url=False,
        )

    async def load_cookie_files(self, cookie_files: list[Path]) -> None:
        if not cookie_files:
            return

        async for cookie in cookies.read_netscape_files(cookie_files):
            self.cookies.update_cookies(cookie)

    async def check_http_status(self, response: aiohttp.ClientResponse | CurlResponse | AbstractResponse[Any]) -> None:
        """Checks the HTTP status code and raises an exception if it's not acceptable."""
        if not isinstance(response, AbstractResponse):
            response = AbstractResponse.create(response)

        if HTTPStatus.OK <= response.status < HTTPStatus.BAD_REQUEST:
            # Check DDosGuard even on successful pages
            await ddos_guard.check_resp(response)
            return

        await _check_json(response)
        await ddos_guard.check_resp(response)
        raise DownloadError(status=response.status)

    @contextlib.asynccontextmanager
    async def request(  # noqa: PLR0913
        self: object,
        url: AbsoluteHttpURL,
        /,
        method: HttpMethod = "GET",
        headers: Mapping[str, str] | None = None,
        *,
        impersonate: str | bool | None = None,
        data: Any = None,
        json: Any = None,
        **request_params: Any,
    ) -> AsyncGenerator[AbstractResponse[Any]]:
        """Make an HTTP request and retry w flaresolverr if required"""
        self = cast("HTTPClient", self)  # noqa: PLW0642
        async with self.raw_request(
            url,
            method,
            headers,
            impersonate=impersonate,
            data=data,
            json=json,
            request_params=request_params,
        ) as resp:
            try:
                await self.check_http_status(resp)
            except DDOSGuardError:
                await resp.aclose()
                if not self.flaresolverr:
                    raise
                yield await self._flaresolverr_request(url, data)
            else:
                yield resp

    @contextlib.asynccontextmanager
    async def raw_request(  # noqa: PLR0913
        self,
        url: AbsoluteHttpURL,
        /,
        method: HttpMethod = "GET",
        headers: Mapping[str, str] | None = None,
        *,
        impersonate: str | bool | None = None,
        data: Any = None,
        json: Any = None,
        request_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[AbstractResponse[Any]]:

        request = Request(
            url=url,
            method=method,
            data=data,
            json=json,
            params=request_params or {},
            headers=prepare_headers(headers),
            impersonate=normalize_impersonation(self.impersonate or impersonate),
        )

        if not request.impersonate:
            _ = request.headers.setdefault("User-Agent", self.config.global_settings.general.user_agent)

        async with self._request(request) as resp:
            yield resp

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
                if self.request_done_callback:
                    self.request_done_callback(request.url, resp, exc)
                del exc
                del resp

    @contextlib.asynccontextmanager
    async def __request(self, request: Request) -> AsyncGenerator[AbstractResponse[Any]]:
        if request.impersonate:
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
                yield AbstractResponse.create(curl_resp)
                self.__sync_session_cookies(request.url)

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
        flaresolverr.verify_solution(self.config.global_settings.general.user_agent, solution)
        return AbstractResponse.create(solution)

    @contextlib.contextmanager
    def json_context(self, check: Callable[[Any, AbstractResponse[Any]], None], /):
        token = _JSON_CHECK.set(check)
        try:
            yield
        finally:
            _JSON_CHECK.reset(token)


async def _check_json(response: AbstractResponse[Any]) -> None:
    if "json" not in response.content_type:
        return

    if check := _JSON_CHECK.get():
        check(await response.json(), response)
        return


class HTTPMixin(ABC):
    @abstractmethod
    @signature.copy(HTTPClient.request)
    def request(self, *args: Any, **kwargs: Any) -> contextlib._AsyncGeneratorContextManager[AbstractResponse[Any]]: ...  # pyright: ignore[reportPrivateUsage]

    @signature.copy(request)
    async def request_json(self, *args: Any, **kwargs: Any) -> Any:
        async with self.request(*args, **kwargs) as resp:
            return await resp.json()

    @signature.copy(request)
    async def request_soup(self, *args: Any, **kwargs: Any) -> BeautifulSoup:
        async with self.request(*args, **kwargs) as resp:
            return await resp.soup()

    @signature.copy(request)
    async def request_text(self, *args: Any, **kwargs: Any) -> str:
        async with self.request(*args, **kwargs) as resp:
            return await resp.text()


def _create_curl_session(config: Config) -> AsyncSession[CurlResponse]:
    loop = asyncio.get_running_loop()

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=CurlCffiWarning)
        acurl = AsyncCurl(loop=loop)

    return AsyncSession(
        loop=loop,
        async_curl=acurl,
        impersonate="chrome",
        verify=bool(config.global_settings.general.ssl_context),
        proxy=str(proxy) if (proxy := config.global_settings.general.proxy) else None,
        timeout=config.global_settings.rate_limiting_options.curl_timeout,
        max_redirects=8,
    )
