from __future__ import annotations

import asyncio
import contextlib
import logging
import platform
import ssl
from base64 import b64encode
from collections import defaultdict
from collections.abc import Generator
from contextvars import ContextVar
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Self

import aiohttp
import certifi
import truststore
from aiohttp import ClientResponse, ClientSession
from aiolimiter import AsyncLimiter

from cyberdrop_dl import ddos_guard, env
from cyberdrop_dl.aio import WeakAsyncLocks
from cyberdrop_dl.clients import HTTPClient
from cyberdrop_dl.clients.download_client import DownloadClient
from cyberdrop_dl.clients.flaresolverr import FlareSolverrClient
from cyberdrop_dl.clients.response import AbstractResponse
from cyberdrop_dl.constants import FileExt
from cyberdrop_dl.cookies import export_cookies, extract_cookies, filter_cookies, read_netscape_files
from cyberdrop_dl.exceptions import DDOSGuardError, DownloadError, ScrapeError, TooManyCrawlerErrors
from cyberdrop_dl.ffmpeg import probe
from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable, Mapping
    from http.cookies import BaseCookie

    from curl_cffi.requests import AsyncSession
    from curl_cffi.requests.models import Response as CurlResponse

    from cyberdrop_dl.managers.manager import Manager

_curl_import_error = None
try:
    from curl_cffi.requests import AsyncSession  # noqa: TC002
except ImportError as e:
    _curl_import_error = e

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

_crawler_errors: dict[str, int] = defaultdict(int)


if TYPE_CHECKING:
    from cyberdrop_dl.managers.manager import Manager

_null_context = contextlib.nullcontext()

_JSON_CHECK: ContextVar[Callable[[Any, AbstractResponse[Any]], None] | None] = ContextVar("_JSON_CHECK", default=None)


class DownloadSpeedLimiter(AsyncLimiter):
    __slots__ = (*AsyncLimiter.__slots__, "chunk_size")

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


class ClientManager:
    """Creates a 'client' that can be referenced by scraping or download sessions."""

    def __init__(self, manager: Manager) -> None:
        self.manager = manager
        ssl_context = self.manager.config.global_settings.general.ssl_context
        if not ssl_context:
            self.ssl_context = False
        elif ssl_context == "certifi":
            self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        elif ssl_context == "truststore":
            self.ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        elif ssl_context == "truststore+certifi":
            self.ssl_context = ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.load_verify_locations(cafile=certifi.where())

        self._cookies: aiohttp.CookieJar | None = None
        self.rate_limits: dict[str, AsyncLimiter] = {}
        self.download_slots: dict[str, int] = {}
        self.global_rate_limiter = AsyncLimiter(self.rate_limiting_options.rate_limit, 1)
        self.global_download_slots = asyncio.Semaphore(self.rate_limiting_options.max_simultaneous_downloads)
        self.scraper_client = HTTPClient.from_client(self)
        self.speed_limiter = DownloadSpeedLimiter(self.rate_limiting_options.download_speed_limit)
        self.download_client = DownloadClient(manager, self)
        self._flaresolverr: FlareSolverrClient | None = None
        self.file_locks: WeakAsyncLocks[str] = WeakAsyncLocks()
        self._session: aiohttp.ClientSession
        self._download_session: aiohttp.ClientSession
        self._curl_session: AsyncSession[CurlResponse]

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
        if _curl_import_error is None:
            self._curl_session = self.new_curl_cffi_session()
        return self

    async def __aexit__(self, *_) -> None:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._session.close())
            tg.create_task(self._download_session.close())
            if self._flaresolverr is not None:
                tg.create_task(self._flaresolverr.aclose())

            if _curl_import_error is None:

                async def close_curl() -> None:
                    try:
                        await self._curl_session.close()
                    except Exception:
                        pass

                tg.create_task(close_curl())

    @property
    def rate_limiting_options(self):
        return self.manager.config.global_settings.rate_limiting_options

    def get_download_slots(self, domain: str) -> int:
        """Returns the download limit for a domain."""

        instances = self.download_slots.get(domain, self.rate_limiting_options.max_simultaneous_downloads_per_domain)

        return min(instances, self.rate_limiting_options.max_simultaneous_downloads_per_domain)

    @staticmethod
    def check_curl_cffi_is_available() -> None:
        if _curl_import_error is None:
            return

        system = "Android" if env.RUNNING_IN_TERMUX else "the system"
        msg = (
            f"curl_cffi is required to scrape this URL but a dependency it's not available on {system}.\n"
            f"See: https://github.com/lexiforest/curl_cffi/issues/74#issuecomment-1849365636\n{_curl_import_error!r}"
        )
        raise ScrapeError("Missing Dependency", msg)

    @staticmethod
    def basic_auth(username: str, password: str) -> str:
        """Returns a basic auth token."""
        token = b64encode(f"{username}:{password}".encode()).decode("ascii")
        return f"Basic {token}"

    def is_allowed_filetype(self, media_item: MediaItem) -> bool:
        """Checks if the file type is allowed to download."""
        ignore_options = self.manager.config.settings.ignore_options
        ext = media_item.ext.lower()

        return not (
            (ignore_options.exclude_images and ext in FileExt.IMAGE)
            or (ignore_options.exclude_videos and ext in FileExt.VIDEO)
            or (ignore_options.exclude_audio and ext in FileExt.AUDIO)
            or (ignore_options.exclude_other and ext not in FileExt.MEDIA)
        )

    def check_allowed_date_range(self, media_item: MediaItem) -> bool:
        """Checks if the file was uploaded within the config date range"""
        datetime = media_item.uploaded_at_date
        if not datetime:
            return True

        item_date = datetime.date()
        ignore_options = self.manager.config.settings.ignore_options

        if ignore_options.exclude_before and item_date < ignore_options.exclude_before:
            return False
        if ignore_options.exclude_after and item_date > ignore_options.exclude_after:
            return False
        return True

    def filter_cookies_by_word_in_domain(self, word: str) -> Iterable[tuple[str, BaseCookie[str]]]:
        """Yields pairs of `[domain, BaseCookie]` for every cookie with a domain that has `word` in it"""
        if not self.cookies:
            return
        self.cookies._do_expiration()
        for domain, _ in self.cookies._cookies:
            if word in domain:
                yield domain, self.cookies.filter_cookies(AbsoluteHttpURL(f"https://{domain}"))

    def new_curl_cffi_session(self) -> AsyncSession[CurlResponse]:
        # Calling code should have validated if curl is actually available
        import warnings

        from curl_cffi.aio import AsyncCurl
        from curl_cffi.requests import AsyncSession
        from curl_cffi.utils import CurlCffiWarning

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
            timeout=self.rate_limiting_options._curl_timeout,
            max_redirects=8,
            cookies={cookie.key: cookie.value for cookie in self.cookies},
        )

    def create_aiohttp_session(
        self,
    ) -> ClientSession:
        return ClientSession(
            headers={
                "User-agent": self.manager.config.global_settings.general.user_agent,
            },
            raise_for_status=False,
            cookie_jar=self.cookies,
            timeout=self.rate_limiting_options._aiohttp_timeout,
            proxy=self.manager.config.global_settings.general.proxy,
            connector=self._new_tcp_connector(),
            requote_redirect_url=False,
        )

    def _new_tcp_connector(self) -> aiohttp.TCPConnector:
        assert DNS_RESOLVER is not None
        conn = aiohttp.TCPConnector(ssl=self.ssl_context, resolver=DNS_RESOLVER())
        conn._resolver_owner = True
        return conn

    def check_domain_errors(self, domain: str) -> None:
        if _crawler_errors[domain] >= env.MAX_CRAWLER_ERRORS:
            if crawler := self.manager.scrape_mapper.disable_crawler(domain):
                msg = (
                    f"{crawler.__class__.__name__} has been disabled after too many errors. "
                    f"URLs from the following domains will be ignored: {crawler.SCRAPE_MAPPER_KEYS}"
                )
                logger.error(msg)
            raise TooManyCrawlerErrors

    @contextlib.contextmanager
    def request_context(self, domain: str) -> Generator[None]:
        self.check_domain_errors(domain)
        try:
            yield
        except DDOSGuardError:
            _crawler_errors[domain] += 1
            raise
        else:
            # we could potentially reset the counter here
            # _crawler_errors[domain] = 0
            pass
        finally:
            pass

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
        """Checks the HTTP status code and raises an exception if it's not acceptable.

        If the response is successful and has valid html, returns soup
        """
        if not isinstance(response, AbstractResponse):
            response = AbstractResponse.create(response)

        message = None

        def check_etag() -> None:
            if download and (e_tag := response.headers.get("ETag", "").strip('"')) in _DOWNLOAD_ERROR_ETAGS:
                message = _DOWNLOAD_ERROR_ETAGS[e_tag]
                raise DownloadError(HTTPStatus.NOT_FOUND, message=message)

        check_etag()
        if HTTPStatus.OK <= response.status < HTTPStatus.BAD_REQUEST:
            # Check DDosGuard even on successful pages
            await ddos_guard.check(response)
            return

        await self._check_json(response)

        await ddos_guard.check(response)
        raise DownloadError(status=response.status, message=message)

    async def _check_json(self, response: AbstractResponse[Any]) -> None:
        if "json" not in response.content_type:
            return

        if check := _JSON_CHECK.get():
            check(await response.json(), response)
            return

    @staticmethod
    def check_content_length(headers: Mapping[str, Any]) -> None:
        content_length, content_type = headers.get("Content-Length"), headers.get("Content-Type")
        if content_length is None or content_type is None:
            return
        if content_length == "322509" and content_type == "video/mp4":
            raise DownloadError(status="Bunkr Maintenance", message="Bunkr under maintenance")
        if content_length == "73003" and content_type == "video/mp4":
            raise DownloadError(410)  # Placeholder video with text "Video removed" (efukt)

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
        logger.warning(f"Unable to setup asynchronous DNS resolver. Falling back to thread based resolver: {e}")
        return aiohttp.ThreadedResolver

    else:
        return aiohttp.AsyncResolver
