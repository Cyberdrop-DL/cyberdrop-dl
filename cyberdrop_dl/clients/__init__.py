from __future__ import annotations

import asyncio
import contextlib
import logging
import platform
import ssl
import time
import uuid
from contextvars import ContextVar
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Protocol, Self, cast, final

import aiohttp
import certifi
import truststore
from aiohttp import ClientResponse, ClientSession
from aiolimiter import AsyncLimiter
from multidict import CIMultiDict

from cyberdrop_dl import constants, cookies, ddos_guard, signature
from cyberdrop_dl.clients import tcp
from cyberdrop_dl.clients.download_client import DownloadClient
from cyberdrop_dl.clients.flaresolverr import FlareSolverrClient
from cyberdrop_dl.clients.response import AbstractResponse
from cyberdrop_dl.cookies import make_simple_cookie
from cyberdrop_dl.exceptions import DDOSGuardError, DownloadError, ScrapeError
from cyberdrop_dl.utils import truncated_preview
from cyberdrop_dl.utils.filepath import sanitize_filename

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Generator, Mapping

    from bs4 import BeautifulSoup
    from curl_cffi.requests import AsyncSession
    from curl_cffi.requests.models import Response as CurlResponse
    from curl_cffi.requests.session import HttpMethod

    from cyberdrop_dl.clients import flaresolverr
    from cyberdrop_dl.manager import Manager
    from cyberdrop_dl.url_objects import AbsoluteHttpURL


_DOWNLOAD_ERROR_ETAGS = {
    "d835884373f4d6c8f24742ceabe74946": "Imgur image has been removed",
    "65b7753c-528a": "SC Scrape Image",
    "5c4fb843-ece": "PixHost Removed Image",
    "637be5da-11d2b": "eFukt Video removed",
    "63a05f27-11d2b": "eFukt Video removed",
    "5a56b09d-1485eb": "eFukt Video removed",
    "19fdf2cd6-383c-5a4cd5b6710ed": "ImageVenue image not Found",
    "383c-5a4cd5b6710ed": "ImageVenue image not Found",
}


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
        if type(content := resp["content"]) is str:
            resp["content"] = truncated_preview(content)
        return resp

    def __str__(self) -> str:
        return str(self.__json__())


_JSON_CHECK: ContextVar[Callable[[Any, AbstractResponse[Any]], None] | None] = ContextVar("_JSON_CHECK", default=None)


class DownloadSpeedLimiter(AsyncLimiter):
    __slots__ = ("chunk_size",)

    def __init__(self, speed_limit: int) -> None:
        self.chunk_size: int = 1024 * 1024 * 10  # 10MB
        if speed_limit:
            self.chunk_size = min(self.chunk_size, speed_limit)
        super().__init__(speed_limit, 1)

    async def acquire(self, amount: float | None = None) -> None:
        if self.max_rate <= 0:
            return
        if not amount:
            amount = self.chunk_size
        await super().acquire(amount)

    def __repr__(self):
        return f"{self.__class__.__name__}(speed_limit={self.max_rate}, chunk_size={self.chunk_size})"


def _make_ssl_context(name: str | None) -> ssl.SSLContext | Literal[False]:
    if not name:
        return False
    if name == "certifi":
        return ssl.create_default_context(cafile=certifi.where())
    if name == "truststore":
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if name == "truststore+certifi":
        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_verify_locations(cafile=certifi.where())
        return ctx
    raise ValueError(name)


class HTTPClient:
    _save_responses_to_disk: bool
    _responses_folder: Path

    def __init__(self, manager: Manager) -> None:
        self.manager = manager
        self.ssl_context = _make_ssl_context(self.manager.config.global_settings.general.ssl_context)
        self._cookies: aiohttp.CookieJar | None = None
        self.rate_limits: dict[str, AsyncLimiter] = {}
        self.global_rate_limiter = AsyncLimiter(self.manager.config.global_settings.rate_limiting_options.rate_limit, 1)
        self.global_download_limiter = asyncio.Semaphore(
            self.manager.config.global_settings.rate_limiting_options.max_simultaneous_downloads
        )

        self.speed_limiter = DownloadSpeedLimiter(
            self.manager.config.global_settings.rate_limiting_options.download_speed_limit
        )
        self.download_client = DownloadClient(manager, self)
        self._flaresolverr: FlareSolverrClient | None = None

        self._session: aiohttp.ClientSession
        self._download_session: aiohttp.ClientSession

        self._curl_session: AsyncSession[CurlResponse] | None = None
        self._save_responses_to_disk = manager.config.settings.files.save_pages_html
        self._responses_folder = manager.config.settings.logs.main_log.parent / "cdl_responses"

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

    @contextlib.contextmanager
    def set_json_checker(self, check: Callable[[Any, AbstractResponse[Any]], None] | None = None) -> Generator[None]:
        token = _JSON_CHECK.set(check)
        try:
            yield
        finally:
            _JSON_CHECK.reset(token)

    @property
    def flaresolverr(self) -> FlareSolverrClient | None:
        if self._flaresolverr is None and (url := self.manager.config.global_settings.general.flaresolverr):
            self._flaresolverr = FlareSolverrClient(url, self._session)
        return self._flaresolverr

    async def __aenter__(self) -> Self:
        await tcp.choose_dns_resolver()
        self._session = self.create_aiohttp_session()
        self._download_session = self.create_aiohttp_session()
        return self

    async def __aexit__(self, *_) -> None:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._session.close())
            tg.create_task(self._download_session.close())
            if self._flaresolverr is not None:
                tg.create_task(self._flaresolverr.aclose())

            if (curl := self._curl_session) is not None:

                async def close_curl() -> None:
                    try:
                        await curl.close()
                    except Exception:
                        pass

                tg.create_task(close_curl())

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

    def create_aiohttp_session(self) -> ClientSession:
        return ClientSession(
            headers={"User-Agent": self.manager.config.global_settings.general.user_agent},
            raise_for_status=False,
            cookie_jar=self.cookies,
            timeout=self.manager.config.global_settings.rate_limiting_options._aiohttp_timeout,
            proxy=self.manager.config.global_settings.general.proxy,
            connector=tcp.new_connector(self.ssl_context),
            requote_redirect_url=False,
        )

    async def load_cookie_files(self, cookie_files: list[Path]) -> None:
        if not cookie_files:
            return

        async for cookie in cookies.read_netscape_files(cookie_files):
            self.cookies.update_cookies(cookie)

    @final
    async def check_http_status(
        self, response: ClientResponse | CurlResponse | AbstractResponse[Any], download: bool = False
    ) -> None:
        """Checks the HTTP status code and raises an exception if it's not acceptable."""
        if not isinstance(response, AbstractResponse):
            response = AbstractResponse.create(response)

        if download:
            _check_etag(response.headers)

        if HTTPStatus.OK <= response.status < HTTPStatus.BAD_REQUEST:
            # Check DDosGuard even on successful pages
            await ddos_guard.check_resp(response)
            return

        await self._check_json(response)
        await ddos_guard.check_resp(response)
        raise DownloadError(status=response.status)

    async def _check_json(self, response: AbstractResponse[Any]) -> None:
        if "json" not in response.content_type:
            return

        if check := _JSON_CHECK.get():
            check(await response.json(), response)
            return

    @property
    def _default_headers(self) -> dict[Any, Any]:
        return {}

    @contextlib.asynccontextmanager
    async def _limiter(self, domain: str) -> AsyncGenerator[None]:
        async with self.global_rate_limiter, self.rate_limits[domain]:
            yield

    def _prepare_headers(self, headers: Mapping[str, str] | None = None) -> CIMultiDict[str]:
        """Add default headers and transform it to CIMultiDict"""
        combined = CIMultiDict(self._default_headers)
        if headers:
            headers = CIMultiDict(headers)
            new: set[str] = set()
            for key, value in headers.items():
                if key in new:
                    combined.add(key, value)
                else:
                    combined[key] = value
                    new.add(key)
        return combined

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
        cache_disabled: bool = False,
        **request_params: Any,
    ) -> AsyncGenerator[AbstractResponse[Any]]:
        self = cast("HTTPClient", self)
        request_params["headers"] = headers = self._prepare_headers(headers)
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
            _ = headers.setdefault("User-agent", self.manager.config.global_settings.general.user_agent)

        async with self.__request(url, method, request_params, impersonate=bool(impersonate)) as resp:
            exc = None
            try:
                yield await self._check_response(resp, url)
            except Exception as e:
                exc = e
                raise
            finally:
                if self._save_responses_to_disk:
                    _ = self.manager.logs.task_group.create_task(
                        asyncio.to_thread(
                            _write_resp_to_disk,
                            self._responses_folder,
                            url,
                            resp,
                            exc,
                        )
                    )

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

    @contextlib.asynccontextmanager
    async def __request(
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
        resp = None
        try:
            if impersonate:
                async with contextlib.aclosing(
                    await self.curl_session.request(method, str(url), stream=True, **request_params)
                ) as curl_resp:
                    resp = AbstractResponse.create(curl_resp)
                    yield resp
                    self.__sync_session_cookies(url)

                return

            async with (
                self._session.request(method, url, **request_params) as aio_resp,
            ):
                resp = AbstractResponse.create(aio_resp)
                yield resp

        finally:
            if resp is not None:
                logger.debug("Finished %s request [id=%s]\n%s", method, request_id, _LazyResponseLog(resp))

    async def _check_response(self, abs_resp: AbstractResponse[Any], url: AbsoluteHttpURL, data: Any | None = None):
        """Checks the HTTP response status and retries DDOS Guard errors with FlareSolverr.

        Returns an AbstractResponse confirmed to not be a DDOS Guard page."""
        try:
            await self.check_http_status(abs_resp)
            return abs_resp
        except DDOSGuardError as e:
            if not (flare := self.flaresolverr):
                raise

            try:
                solution = await flare.request(url, data)
            except RuntimeError:
                raise e from None

            self.cookies.update_cookies(solution.cookies)
            await _check_flaresolverr_resp(self.manager.config.global_settings.general.user_agent, solution)
            return AbstractResponse.create(solution)


async def _check_flaresolverr_resp(cdl_user_agent: str, solution: flaresolverr.Solution) -> None:
    mismatch_ua_msg = (
        "Config user_agent and flaresolverr user_agent do not match:"
        f"\n  Cyberdrop-DL: '{cdl_user_agent}'"
        f"\n  Flaresolverr: '{solution.user_agent}'"
    )

    try:
        ddos_guard.check_html(solution.content)
    except DDOSGuardError:
        if solution.user_agent != cdl_user_agent:
            raise DDOSGuardError(mismatch_ua_msg) from None

    if solution.user_agent != cdl_user_agent:
        logger.warning(f"{mismatch_ua_msg}\n Response was successful but cookies will not be valid")


def _write_resp_to_disk(
    folder: Path,
    url: AbsoluteHttpURL,
    response: AbstractResponse[Any],
    exc: Exception | None = None,
) -> None:

    max_stem_len = 245 - len(str(folder)) + len(constants.STARTUP_TIME_STR) + 10

    log_date = response.created_at.strftime(constants.LOGS_DATETIME_FORMAT)
    path_safe_url = sanitize_filename(Path(str(url)).as_posix().replace("/", "-"))
    filename = f"{path_safe_url[:max_stem_len]}_{log_date}.html"
    file = folder / filename
    content = response.create_report(exc)
    try:
        _ = file.write_text(content, "utf8")
    except OSError:
        pass


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

        with self.client.set_json_checker(self.__json_resp_check__):
            async with (
                self.client._limiter(self.DOMAIN),
                self.client.request(*args, impersonate=impersonate, **kwargs) as resp,
            ):
                yield resp

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


def _check_etag(headers: Mapping[str, str]) -> None:
    e_tag = headers.get("ETag", "").strip('"')
    if message := _DOWNLOAD_ERROR_ETAGS.get(e_tag):
        raise DownloadError(HTTPStatus.NOT_FOUND, message)
