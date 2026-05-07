from __future__ import annotations

import asyncio
import contextlib
import logging
import platform
import ssl
from contextvars import ContextVar
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Literal, Self

import aiohttp
import certifi
import truststore
from aiohttp import ClientResponse, ClientSession
from aiolimiter import AsyncLimiter

from cyberdrop_dl import ddos_guard
from cyberdrop_dl.clients import HTTPClient
from cyberdrop_dl.clients.download_client import DownloadClient
from cyberdrop_dl.clients.flaresolverr import FlareSolverrClient
from cyberdrop_dl.clients.response import AbstractResponse
from cyberdrop_dl.constants import FileExt
from cyberdrop_dl.cookies import export_cookies, extract_cookies, filter_cookies, read_netscape_files
from cyberdrop_dl.exceptions import DownloadError, ScrapeError
from cyberdrop_dl.ffmpeg import probe

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Mapping

    from curl_cffi.requests import AsyncSession
    from curl_cffi.requests.models import Response as CurlResponse

    from cyberdrop_dl.manager import Manager
    from cyberdrop_dl.url_objects import MediaItem


logger = logging.getLogger(__name__)

DNS_RESOLVER: type[aiohttp.AsyncResolver] | type[aiohttp.ThreadedResolver] | None = None
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


if TYPE_CHECKING:
    from cyberdrop_dl.manager import Manager

_null_context = contextlib.nullcontext()

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


class ClientManager:
    """Creates a 'client' that can be referenced by scraping or download sessions."""

    def __init__(self, manager: Manager) -> None:
        self.manager = manager
        self.ssl_context = _make_ssl_context(self.manager.config.global_settings.general.ssl_context)
        self._cookies: aiohttp.CookieJar | None = None
        self.rate_limits: dict[str, AsyncLimiter] = {}
        self.download_slots: dict[str, int] = {}
        self.global_rate_limiter = AsyncLimiter(self.manager.config.global_settings.rate_limiting_options.rate_limit, 1)
        self.global_download_slots = asyncio.Semaphore(
            self.manager.config.global_settings.rate_limiting_options.max_simultaneous_downloads
        )
        self.scraper_client = HTTPClient.from_client(self)
        self.speed_limiter = DownloadSpeedLimiter(
            self.manager.config.global_settings.rate_limiting_options.download_speed_limit
        )
        self.download_client = DownloadClient(manager, self)
        self._flaresolverr: FlareSolverrClient | None = None

        self._session: aiohttp.ClientSession
        self._download_session: aiohttp.ClientSession

        self._curl_session: AsyncSession[CurlResponse] | None = None

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
        global DNS_RESOLVER
        if DNS_RESOLVER is None:
            DNS_RESOLVER = await _get_dns_resolver()  # pyright: ignore[reportConstantRedefinition]

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

    def get_download_slots(self, domain: str) -> int:
        """Returns the download limit for a domain."""

        instances = self.download_slots.get(
            domain, self.manager.config.global_settings.rate_limiting_options.max_simultaneous_downloads_per_domain
        )

        return min(
            instances, self.manager.config.global_settings.rate_limiting_options.max_simultaneous_downloads_per_domain
        )

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
        assert DNS_RESOLVER is not None
        tcp_conn = aiohttp.TCPConnector(ssl=self.ssl_context, resolver=DNS_RESOLVER())
        tcp_conn._resolver_owner = True

        return ClientSession(
            headers={
                "User-Agent": self.manager.config.global_settings.general.user_agent,
            },
            raise_for_status=False,
            cookie_jar=self.cookies,
            timeout=self.manager.config.global_settings.rate_limiting_options._aiohttp_timeout,
            proxy=self.manager.config.global_settings.general.proxy,
            connector=tcp_conn,
            requote_redirect_url=False,
        )

    async def load_cookie_files(self) -> None:
        if self.manager.config.settings.browser_cookies.auto_import:
            assert self.manager.config.settings.browser_cookies.browser
            cookies = await extract_cookies(self.manager.config.settings.browser_cookies.browser)
            await export_cookies(
                filter_cookies(cookies, self.manager.config.settings.browser_cookies.sites),
                output_path=self.manager.appdata.cookies,
            )

        cookie_files = await asyncio.to_thread(lambda: sorted(self.manager.appdata.cookies.glob("*.txt")))
        if not cookie_files:
            return

        async for cookie in read_netscape_files(cookie_files):
            self.cookies.update_cookies(cookie)

    def get_rate_limiter(self, domain: str) -> AsyncLimiter:
        """Get a rate limiter for a domain."""
        if domain in self.rate_limits:
            return self.rate_limits[domain]
        return self.rate_limits["other"]

    async def check_http_status(
        self,
        response: ClientResponse | CurlResponse | AbstractResponse[Any],
        download: bool = False,
    ) -> None:
        """Checks the HTTP status code and raises an exception if it's not acceptable."""
        if not isinstance(response, AbstractResponse):
            response = AbstractResponse.create(response)

        if download:
            _check_etag(response.headers)

        if HTTPStatus.OK <= response.status < HTTPStatus.BAD_REQUEST:
            # Check DDosGuard even on successful pages
            await ddos_guard.check(response)
            return

        await self._check_json(response)

        await ddos_guard.check(response)
        raise DownloadError(status=response.status)

    async def _check_json(self, response: AbstractResponse[Any]) -> None:
        if "json" not in response.content_type:
            return

        if check := _JSON_CHECK.get():
            check(await response.json(), response)
            return

    async def check_file_duration(self, media_item: MediaItem) -> bool:
        """Checks the file runtime against the config runtime limits."""
        if media_item.is_segment:
            return True

        is_video = media_item.ext.lower() in FileExt.VIDEO
        is_audio = media_item.ext.lower() in FileExt.AUDIO
        if not (is_video or is_audio):
            return True

        duration_limits = self.manager.config.settings.media_duration_limits
        min_video_duration: float = duration_limits.minimum_video_duration.total_seconds()
        max_video_duration: float = duration_limits.maximum_video_duration.total_seconds()
        min_audio_duration: float = duration_limits.minimum_audio_duration.total_seconds()
        max_audio_duration: float = duration_limits.maximum_audio_duration.total_seconds()
        video_duration_limits = min_video_duration, max_video_duration
        audio_duration_limits = min_audio_duration, max_audio_duration

        if is_video and not any(video_duration_limits):
            return True
        if is_audio and not any(audio_duration_limits):
            return True

        async def get_duration() -> float | None:
            if media_item.duration:
                return media_item.duration

            if media_item.downloaded:
                properties = await probe(media_item.path)

            else:
                properties = await probe(media_item.url, headers=media_item.headers)

            if properties.format.duration:
                return properties.format.duration
            if is_video and properties.video:
                return properties.video.duration
            if is_audio and properties.audio:
                return properties.audio.duration

        duration: float | None = await get_duration()
        media_item.duration = duration

        if duration is None:
            return True

        await self.manager.database.history.add_duration(media_item.domain, media_item)

        if is_video:
            max_video_duration = max_video_duration or float("inf")

            return min_video_duration <= duration <= max_video_duration

        max_audio_duration = max_audio_duration or float("inf")
        return min_audio_duration <= duration <= max_audio_duration


async def _get_dns_resolver(
    loop: asyncio.AbstractEventLoop | None = None,
) -> type[aiohttp.AsyncResolver] | type[aiohttp.ThreadedResolver]:
    """Test aiodns with a DNS lookup."""

    # pycares (the underlying C extension that aiodns uses) installs successfully in most cases,
    # but it fails to actually connect to DNS servers on some platforms (e.g., Android).

    if (system := platform.system()) in ("Windows", "Android"):
        logger.warning(
            f"Unable to setup asynchronous DNS resolver. Falling back to thread based resolver. Reason: not supported on {system}"
        )
        return aiohttp.ThreadedResolver

    try:
        import aiodns

        async with aiodns.DNSResolver(loop=loop, timeout=5.0) as resolver:
            _ = await resolver.query_dns("github.com", "A")

    except Exception as e:
        logger.warning(f"Unable to setup asynchronous DNS resolver. Falling back to thread based resolver: {e!r}")
        return aiohttp.ThreadedResolver

    else:
        return aiohttp.AsyncResolver


def _check_etag(headers: Mapping[str, str]) -> None:
    e_tag = headers.get("ETag", "").strip('"')
    if message := _DOWNLOAD_ERROR_ETAGS.get(e_tag):
        raise DownloadError(HTTPStatus.NOT_FOUND, message)
