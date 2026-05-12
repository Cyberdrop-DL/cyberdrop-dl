from __future__ import annotations

import asyncio
import contextlib
import logging
import platform
import time
import uuid
from contextvars import ContextVar
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, Self, cast, final

import aiohttp
from multidict import CIMultiDict

from cyberdrop_dl import aio, cookies, ddos_guard, signature
from cyberdrop_dl.clients import flaresolverr, tcp
from cyberdrop_dl.clients.response import AbstractResponse
from cyberdrop_dl.cookies import make_simple_cookie
from cyberdrop_dl.exceptions import DDOSGuardError, DownloadError, ScrapeError
from cyberdrop_dl.utils import truncated_preview

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Mapping
    from pathlib import Path

    from bs4 import BeautifulSoup
    from curl_cffi.requests import AsyncSession
    from curl_cffi.requests.models import Response as CurlResponse
    from curl_cffi.requests.session import HttpMethod

    from cyberdrop_dl.manager import Manager
    from cyberdrop_dl.url_objects import AbsoluteHttpURL

_JSON_CHECK: ContextVar[Callable[[Any, AbstractResponse[Any]], None] | None] = ContextVar("_JSON_CHECK", default=None)

logger = logging.getLogger(__name__)


class _LazyRequestLog:
    def __init__(self, params: Mapping[str, Any]) -> None:
        self.params: Mapping[str, Any] = params

    def __json__(self) -> dict[str, Any]:
        params = {k: v for k, v in self.params.items() if v is not None}
        headers = dict(params.pop("headers")) or None
        if headers:
            params.update(headers=headers)
        return params

    def __str__(self) -> str:
        return str(self.__json__())


class _LazyResponseLog:
    def __init__(self, response: AbstractResponse[Any]) -> None:
        self.response = response

    def __json__(self) -> dict[str, Any]:
        resp = self.response.__json__()
        del resp["created_at"]
        if type(resp["content"]) is str:
            resp["content"] = truncated_preview(resp["content"])
        return resp

    def __str__(self) -> str:
        return str(self.__json__())


@final
class HTTPClient:
    def __init__(self, manager: Manager) -> None:
        self.manager = manager
        self.ssl_context = tcp.create_ssl_context(self.manager.config.global_settings.general.ssl_context)
        self.rate_limits: dict[str, aio.RateLimiter] = {}
        self.global_rate_limiter = aio.RateLimiter.w_no_burst(
            self.manager.config.global_settings.rate_limiting_options.rate_limit
        )
        self.global_download_limiter = asyncio.Semaphore(
            self.manager.config.global_settings.rate_limiting_options.max_simultaneous_downloads
        )

        self._cookies: aiohttp.CookieJar | None = None
        self._dump_responses: bool = (
            manager.config.settings.files.save_pages_html or manager.config.settings.files.dump_responses
        )
        self._flaresolverr: flaresolverr.Client | None = None
        self._curl_session: AsyncSession[CurlResponse] | None = None
        self._session: aiohttp.ClientSession
        self._download_session: aiohttp.ClientSession

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
        if self._flaresolverr is None and (url := self.manager.config.global_settings.general.flaresolverr):
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

    async def __aexit__(self, *_) -> None:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._download_session.close())
            if self._curl_session is not None:
                tg.create_task(self._curl_session.close())

            if self._flaresolverr is not None:
                # close before closing aiohttp session
                await self._flaresolverr.aclose()
            await self._session.close()

    def _create_curl_session(self) -> AsyncSession[CurlResponse]:
        try:
            from curl_cffi.aio import AsyncCurl
            from curl_cffi.requests import AsyncSession
            from curl_cffi.utils import CurlCffiWarning
        except ImportError as e:
            msg = (
                f"curl_cffi is required to scrape this URL but a dependency it's not available on {platform.system()}.\n"
                f"See: https://github.com/lexiforest/curl_cffi/issues/74#issuecomment-1849365636\n{e!r}"
            )
            raise ScrapeError("Missing Dependency", msg) from e

        import warnings

        loop = asyncio.get_running_loop()

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=CurlCffiWarning)
            acurl = AsyncCurl(loop=loop)

        proxy_or_none = str(proxy) if (proxy := self.manager.config.global_settings.general.proxy) else None

        return AsyncSession(
            loop=loop,
            async_curl=acurl,
            impersonate="chrome",
            verify=bool(self.ssl_context),
            proxy=proxy_or_none,
            timeout=self.manager.config.global_settings.rate_limiting_options._curl_timeout,
            max_redirects=8,
            cookies={cookie.key: cookie.value for cookie in self.cookies},
        )

    def create_aiohttp_session(self) -> aiohttp.ClientSession:
        return aiohttp.ClientSession(
            headers={"User-Agent": self.manager.config.global_settings.general.user_agent},
            raise_for_status=False,
            cookie_jar=self.cookies,
            timeout=self.manager.config.global_settings.rate_limiting_options._aiohttp_timeout,
            proxy=self.manager.config.global_settings.general.proxy,
            connector=tcp.create_connector(self.ssl_context),
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
    async def request(
        self: object,
        url: AbsoluteHttpURL,
        /,
        method: HttpMethod = "GET",
        headers: Mapping[str, str] | None = None,
        impersonate: str | bool | None = None,
        data: Any = None,
        json: Any = None,
        **request_params: Any,
    ) -> AsyncGenerator[AbstractResponse[Any]]:
        """Make an HTTP request and retry w flaresolverr if required"""
        self = cast("HTTPClient", self)
        async with self.raw_request(url, method, headers, impersonate, data, json, request_params) as resp:
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
    async def raw_request(
        self,
        url: AbsoluteHttpURL,
        /,
        method: HttpMethod = "GET",
        headers: Mapping[str, str] | None = None,
        impersonate: str | bool | None = None,
        data: Any = None,
        json: Any = None,
        request_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[AbstractResponse[Any]]:
        request_params = request_params or {}
        request_params["headers"] = headers = _prepare_headers(headers)
        request_params["data"] = data
        request_params["json"] = json

        if method == "GET" and (data or json):
            method = "POST"

        impersonate = self.manager.cli_args.impersonate or impersonate
        if impersonate:
            if impersonate is True:
                impersonate = "chrome"
            request_params["impersonate"] = impersonate

        else:
            _ = headers.setdefault("User-Agent", self.manager.config.global_settings.general.user_agent)

        async with self._request(url, method, request_params, impersonate=bool(impersonate)) as resp:
            yield resp

    @contextlib.asynccontextmanager
    async def _request(
        self,
        url: AbsoluteHttpURL,
        method: HttpMethod,
        request_params: Mapping[str, Any],
        *,
        impersonate: bool,
    ) -> AsyncGenerator[AbstractResponse[Any]]:
        request_id = str(uuid.uuid4())
        logger.debug(
            "Starting %s request [id=%s] to %s \n%s",
            method,
            request_id,
            url,
            _LazyRequestLog(request_params),
        )
        exc = None
        async with self.__request(url, method, request_params, impersonate=impersonate) as resp:
            resp.id = request_id
            logger.debug("Finished %s request [id=%s]\n%s", method, request_id, _LazyResponseLog(resp))
            try:
                yield resp
            except Exception as e:
                exc = e
                raise
            finally:
                if self._dump_responses:
                    self.manager.logs.write_response(url, resp, exc)
                del exc
                del resp

    @contextlib.asynccontextmanager
    async def __request(
        self,
        url: AbsoluteHttpURL,
        method: HttpMethod,
        request_params: Mapping[str, Any],
        *,
        impersonate: bool,
    ) -> AsyncGenerator[AbstractResponse[Any]]:

        if impersonate:
            async with contextlib.aclosing(
                await self.curl_session.request(method, str(url), stream=True, **request_params)
            ) as curl_resp:
                yield AbstractResponse.create(curl_resp)
                self.__sync_session_cookies(url)

            return

        async with self._session.request(method, url, **request_params) as aio_resp:
            yield AbstractResponse.create(aio_resp)

    async def _flaresolverr_request(
        self,
        url: AbsoluteHttpURL,
        data: Any | None = None,
    ):
        """Make a request with FlareSolverr.

        Returns an AbstractResponse confirmed to not be a DDOS Guard page, even if flaresolverr fails to detect/solve a challenge"""

        assert self.flaresolverr
        solution = await self.flaresolverr.request(url, data)
        self.cookies.update_cookies(solution.cookies)
        flaresolverr.verify_solution(self.manager.config.global_settings.general.user_agent, solution)
        return AbstractResponse.create(solution)


async def _check_json(response: AbstractResponse[Any]) -> None:
    if "json" not in response.content_type:
        return

    if check := _JSON_CHECK.get():
        check(await response.json(), response)
        return


def _prepare_headers(headers: Mapping[str, str] | None) -> CIMultiDict[str]:
    return CIMultiDict(headers) if headers else CIMultiDict()


class HTTPClientProxy(Protocol):
    DOMAIN: ClassVar[str]
    _IMPERSONATE: ClassVar[str | bool | None] = None

    @property
    def client(self) -> HTTPClient: ...

    @classmethod
    def __json_resp_check__(cls, json_resp: Any, resp: AbstractResponse[Any], /) -> None:
        """Custom check for JSON responses.

        This method is called automatically by the `HttpClient` when a JSON response is received from `cls.DOMAIN`
        and it was **NOT** successful (`4xx` or `5xx` HTTP code).

        Override this method in subclasses to raise a custom `ScrapeError` instead of the default HTTP error

        Example:
            ```python
            if isinstance(json, dict) and json.get("status") == "error":
                raise ScrapeError(422, f"API error: {json['message']}")
            ```

        IMPORTANT:
            Cases were the response **IS** successful (200, OK) but the JSON indicates an error
            should be handled by the crawler itself
        """

    @signature.copy(HTTPClient.request)
    @contextlib.asynccontextmanager
    async def request(
        self, *args, impersonate: str | bool | None = None, **kwargs
    ) -> AsyncGenerator[AbstractResponse[Any]]:
        if impersonate is None:
            impersonate = self._IMPERSONATE

        token = _JSON_CHECK.set(self.__json_resp_check__)
        try:
            async with (
                self.client.global_rate_limiter,
                self.client.rate_limits[self.DOMAIN],
                self.client.request(*args, impersonate=impersonate, **kwargs) as resp,
            ):
                yield resp
        finally:
            _JSON_CHECK.reset(token)

    @signature.copy(request)
    async def request_json(self, *args, **kwargs) -> Any:
        async with self.request(*args, **kwargs) as resp:
            return await resp.json()

    @signature.copy(request)
    async def request_soup(self, *args, **kwargs) -> BeautifulSoup:
        async with self.request(*args, **kwargs) as resp:
            return await resp.soup()

    @signature.copy(request)
    async def request_text(self, *args, **kwargs) -> str:
        async with self.request(*args, **kwargs) as resp:
            return await resp.text()
