from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import datetime
import importlib
import logging
import pkgutil
import re
import weakref
from abc import ABC, abstractmethod
from collections import Counter
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, Concatenate, Final, Literal, ParamSpec, Self, TypeVar, final

from aiolimiter import AsyncLimiter
from typing_extensions import deprecated

from cyberdrop_dl import env
from cyberdrop_dl.clients import HTTPClient, HTTPClientProxy
from cyberdrop_dl.crawlers._hls import HLSParser
from cyberdrop_dl.downloader.downloader import Downloader
from cyberdrop_dl.exceptions import MaxChildrenError, NoExtensionError, ScrapeError
from cyberdrop_dl.mediaprops import ISO639Subtitle, Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem, ScrapeItem
from cyberdrop_dl.utils import (
    css,
    dates,
    error_handling_context,
    error_handling_wrapper,
    get_download_path,
    is_absolute_http_url,
    is_blob_or_svg,
    m3u8,
    parse_url,
)
from cyberdrop_dl.utils.filepath import compose_filename, get_filename_and_ext, remove_file_id
from cyberdrop_dl.utils.strings import safe_format

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Callable, Coroutine, Generator, Iterable, Mapping
    from types import ModuleType

    import yarl
    from bs4 import BeautifulSoup, Tag
    from curl_cffi.requests.impersonate import BrowserTypeLiteral

    from cyberdrop_dl.managers.manager import Manager

logger = logging.getLogger(__name__)

_P = ParamSpec("_P")
_R = TypeVar("_R")
_T = TypeVar("_T")

OneOrTuple = _T | tuple[_T, ...]
SupportedPaths = dict[str, OneOrTuple[str]]
SupportedDomains = OneOrTuple[str]
RateLimit = tuple[float, float]
SKIP_DOWNLOAD: ContextVar[bool] = ContextVar("SKIP_DOWNLOAD", default=False)


_HASH_PREFIXES = "md5:", "sha1:", "sha256:", "xxh128:"


@dataclasses.dataclass(slots=True, frozen=True)
class _PlaceHolderConfigInclude:
    file_id: bool = True
    video_codec: bool = True
    audio_codec: bool = True
    resolution: bool = True
    fps: bool = True
    hash: bool = True


_include = _PlaceHolderConfigInclude()


_DB_PATH_BUILDERS: MappingProxyType[str, Callable[[AbsoluteHttpURL], str]] = MappingProxyType(
    {
        "url": lambda url: str(url),
        "name": lambda url: url.name,
        "path": lambda url: url.path,
        "path_qs": lambda url: url.path_qs,
        "path_qs_frag": lambda url: f"{url.path_qs}#{frag}" if (frag := url.fragment) else url.path_qs,
        "path_frag": lambda url: f"{url.path}#{frag}" if (frag := url.fragment) else url.path,
    }
)


def _url(item: ScrapeItem | AbsoluteHttpURL) -> AbsoluteHttpURL:
    return item if isinstance(item, AbsoluteHttpURL) else item.url


@dataclasses.dataclass(slots=True, frozen=True, order=True)
class CrawlerInfo:
    site: str
    primary_url: AbsoluteHttpURL
    supported_domains: tuple[str, ...]
    supported_paths: SupportedPaths

    @classmethod
    def generic(cls, name: str, paths: SupportedPaths) -> Self:
        return cls(name, "::GENERIC CRAWLER::", (), paths)  # pyright: ignore[reportArgumentType]


class Registry:
    abc: weakref.WeakSet[type[Crawler]] = weakref.WeakSet()
    concrete: weakref.WeakSet[type[Crawler]] = weakref.WeakSet()
    generic: weakref.WeakSet[type[Crawler]] = weakref.WeakSet()
    # generics are concrete crawlers that are not bound to any specific site
    # They can be mapped to a site by just subclassing and setting a PRIMARY URL. ex: Chevereto

    _loaded: bool = False

    @classmethod
    def import_all(cls) -> None:
        if cls._loaded:
            return

        assert __package__
        module = importlib.import_module(__package__)
        cls._import_from(module)
        cls._loaded = True

    @classmethod
    def _import_from(cls, module: ModuleType) -> None:
        """Import every module (and sub-package) inside *pkg_name*."""
        for sub_module_info in pkgutil.iter_modules(module.__path__, module.__name__ + "."):
            sub_module = importlib.import_module(sub_module_info.name)
            if sub_module_info.ispkg:
                cls._import_from(sub_module)


class _CrawlerLogger(logging.LoggerAdapter[logging.Logger]):
    def __init__(self, crawler_name: str) -> None:
        self._crawler_name: str = crawler_name
        super().__init__(logger)

    def process(self, msg: object, kwargs: Any) -> tuple[str, Any]:
        return f"[{self._crawler_name}] {msg}", kwargs


class Crawler(HTTPClientProxy, HLSParser, ABC):
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ()
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = ()
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {}
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date} - {id} - {title}"

    UPDATE_UNSUPPORTED: ClassVar[bool] = False
    ALLOW_EMPTY_PATH: ClassVar[bool] = False
    NEXT_PAGE_SELECTOR: ClassVar[str] = ""

    DEFAULT_TRIM_URLS: ClassVar[bool] = True
    FOLDER_DOMAIN: ClassVar[str] = ""
    DOMAIN: ClassVar[str]
    PRIMARY_URL: ClassVar[AbsoluteHttpURL]

    _RATE_LIMIT: ClassVar[RateLimit] = 25, 1
    _DOWNLOAD_SLOTS: ClassVar[int | None] = None
    _USE_DOWNLOAD_SERVERS_LOCKS: ClassVar[bool] = False
    disabled: bool = False

    @staticmethod
    def __db_path__(url: AbsoluteHttpURL, /) -> str:
        return url.path

    @final
    def __init__(self, manager: Manager) -> None:
        self.manager: Manager = manager
        self.downloader: Downloader = dataclasses.field(init=False)
        self.client: HTTPClient = dataclasses.field(init=False)
        self._startup_lock: asyncio.Lock = asyncio.Lock()
        self._ready: bool = False
        self._logged_in: bool = False
        self._scraped_items: set[str] = set()

        self._logger: _CrawlerLogger = _CrawlerLogger(self.FOLDER_DOMAIN)
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(20)
        self.__post_init__()

    def __post_init__(self) -> None:
        """Override in subclasses to add custom init logic

        This method gets called inmediatly on class creation"""

    @final
    async def __async_init__(self) -> None:
        if self._ready:
            return
        async with self._startup_lock:
            if self._ready:
                return
            self.client = self.manager.client_manager.scraper_client
            self.manager.client_manager.rate_limits[self.DOMAIN] = AsyncLimiter(*self._RATE_LIMIT)
            if self._DOWNLOAD_SLOTS:
                self.manager.client_manager.download_slots[self.DOMAIN] = self._DOWNLOAD_SLOTS
            if self._USE_DOWNLOAD_SERVERS_LOCKS:
                self.manager.client_manager.download_client.server_locked_domains.add(self.DOMAIN)
            self.__init_downloader__()
            await self.__async_post_init__()
            self._ready = True

    async def __async_post_init__(self) -> None:
        """Perform additional setup that requires I/O

        ex: login, getting API tokens, etc..

        This method its called once and only if the crawler is actually going to be scrape something"""

    def __init_subclass__(
        cls,
        is_abc: bool = False,
        is_generic: bool = False,
        is_debug: bool = False,
        db_path: Literal["url", "name", "path", "path_qs", "path_qs_frag", "path_frag"] | None = None,
        **kwargs,
    ) -> None:
        super().__init_subclass__(**kwargs)

        assert cls.__init__ is Crawler.__init__, (
            f"Subclass {cls.__name__} must not override __init__,use __post_init__ for additional setup"
        )

        assert cls.__async_init__ is Crawler.__async_init__, (
            f"Subclass {cls.__name__} must not override __async_init__,"
            "use __async_post_init__ for setup that requires manipulating cookies or any IO (database access, HTTP requests, etc...)"
        )

        cls.NAME: str = cls.__name__.removesuffix("Crawler")
        cls.IS_GENERIC: bool = is_generic
        cls.SUPPORTED_PATHS = _sort_supported_paths(cls.SUPPORTED_PATHS)  # pyright: ignore[reportConstantRedefinition]
        cls.IS_ABC: bool = is_abc

        add_to_register = bool(not is_debug or (is_debug and env.ENABLE_DEBUG_CRAWLERS))

        if db_path:
            cls.__db_path__ = staticmethod(_DB_PATH_BUILDERS[db_path])

        if cls.IS_GENERIC:
            cls.SCRAPE_MAPPER_KEYS = ()
            cls.INFO: CrawlerInfo = CrawlerInfo.generic(cls.NAME, cls.SUPPORTED_PATHS)
            if add_to_register:
                Registry.generic.add(cls)
            return

        if is_abc:
            if add_to_register:
                Registry.abc.add(cls)
            return

        if cls.NAME != "RealDebrid":
            Crawler._assert_fields_overrides(cls, "PRIMARY_URL", "DOMAIN", "SUPPORTED_PATHS")

        cls.REPLACE_OLD_DOMAINS_REGEX: str | None = "|".join(cls.OLD_DOMAINS) if cls.OLD_DOMAINS else None
        if cls.OLD_DOMAINS:
            supported_domains = cls.SUPPORTED_DOMAINS or ()
            if isinstance(supported_domains, str):
                supported_domains = (supported_domains,)

            cls.SUPPORTED_DOMAINS = tuple(sorted({*cls.OLD_DOMAINS, *supported_domains, cls.PRIMARY_URL.host}))  # pyright: ignore[reportConstantRedefinition]

        _validate_supported_paths(cls)
        cls.SCRAPE_MAPPER_KEYS: tuple[str, ...] = _make_scrape_mapper_keys(cls)  # pyright: ignore[reportConstantRedefinition]
        cls.FOLDER_DOMAIN = cls.FOLDER_DOMAIN or cls.DOMAIN.capitalize()  # pyright: ignore[reportConstantRedefinition]
        cls.INFO = CrawlerInfo(  # pyright: ignore[reportConstantRedefinition]
            site=cls.FOLDER_DOMAIN,
            primary_url=cls.PRIMARY_URL,
            supported_domains=_make_wiki_supported_domains(cls.SCRAPE_MAPPER_KEYS),
            supported_paths=cls.SUPPORTED_PATHS,
        )
        if add_to_register:
            Registry.concrete.add(cls)

    def __init_downloader__(self) -> None:
        self.downloader = dl = Downloader(self.manager, self.DOMAIN)
        dl.startup()

    @final
    @staticmethod
    def _assert_fields_overrides(subclass: type[Crawler], *fields: str) -> None:
        for field_name in fields:
            assert getattr(subclass, field_name, None), f"Subclass {subclass.__name__} must override: {field_name}"

    @final
    def create_task(self, coro: Coroutine[Any, Any, _T]) -> None:
        _ = self.manager.scrape_mapper.create_task(coro)

    @abstractmethod
    async def fetch(self, scrape_item: ScrapeItem) -> None:
        """Here goes the main logic to parse URL paths.

        This method MUST NOT raise any exceptions other that ValueError to indicate that the path is not supported"""

    @final
    @property
    def log(self) -> _CrawlerLogger:
        return self._logger

    @final
    @property
    def waiting_items(self) -> int:
        if self._semaphore._waiters is None:
            return 0
        return len(self._semaphore._waiters)

    @final
    @property
    def deep_scrape(self) -> bool:
        return self.manager.config.deep_scrape

    @property
    def allow_no_extension(self) -> bool:
        return not self.manager.config.settings.ignore_options.exclude_files_with_no_extension

    @property
    def separate_posts(self) -> bool:
        return self.manager.config.settings.download_options.separate_posts

    @final
    @contextlib.contextmanager
    def disable_on_error(self, msg: str) -> Generator[None]:
        try:
            yield
        except Exception:
            self.log.error(f"{msg}. Crawler has been disabled")
            self.disabled = True
            raise

    catch_errors: Final = error_handling_context

    @final
    async def run(self, scrape_item: ScrapeItem) -> None:
        if self.disabled:
            return

        async with self._semaphore:
            with scrape_item.track_changes():
                scrape_item.url = url = self.transform_url(scrape_item.url)

            if url.path_qs in self._scraped_items:
                logger.info(f"Skipping {url} as it has already been scraped")
                return

            self._scraped_items.add(url.path_qs)

            with self.new_task_id(scrape_item.url):
                try:
                    if not self.ALLOW_EMPTY_PATH and scrape_item.url.path == "/":
                        raise ValueError
                    await self.fetch(scrape_item)
                except ValueError:
                    self.raise_exc(scrape_item, ScrapeError("Unknown URL path"))
                except MaxChildrenError as e:
                    self.raise_exc(scrape_item, e)

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        """Transforms an URL before it reaches the fetch method

        Override it to transform thumbnail URLs into full res URLs or URLs in an old unsupported format into a new one"""
        if cls.REPLACE_OLD_DOMAINS_REGEX is not None:
            new_host = re.sub(cls.REPLACE_OLD_DOMAINS_REGEX, cls.PRIMARY_URL.host, url.host)
            return url.with_host(new_host)
        return url

    @error_handling_wrapper
    def raise_exc(self, scrape_item: ScrapeItem, exc: type[Exception] | Exception | str) -> None:
        if isinstance(exc, str):
            exc = ScrapeError(exc)
        raise exc

    @final
    def new_task_id(self, url: AbsoluteHttpURL):
        """Creates a new task_id (shows the URL in the UI and logs)"""
        self.log.info(f"Scraping {url}")
        return self.manager.scrape_mapper.tui.scrape.new(url)

    @final
    @staticmethod
    def is_subdomain(url: AbsoluteHttpURL) -> bool:
        return url.host.removeprefix("www.").count(".") > 1

    @classmethod
    def is_self_subdomain(cls, url: AbsoluteHttpURL) -> bool:
        primary_domain = cls.PRIMARY_URL.host.removeprefix("www.")
        other_domain = url.host.removeprefix("www.")
        if primary_domain == other_domain:
            return False
        return primary_domain in other_domain and other_domain.count(".") > primary_domain.count(".")

    @final
    async def write_metadata(self, scrape_item: ScrapeItem, name: str, metadata: object) -> None:
        """Write general metadata (not specific to a single file) to json output"""

        filename = f"{name}.metadata"  # we won't write to fs, so we skip name sanitization
        download_folder = get_download_path(self.manager, scrape_item, self.FOLDER_DOMAIN)
        url = AbsoluteHttpURL(scrape_item.url.with_scheme("metadata"))
        media_item = MediaItem.from_item(
            scrape_item,
            url,
            self.DOMAIN,
            db_path="",
            download_folder=download_folder,
            filename=filename,
        )
        media_item.metadata = metadata
        await self.__write_to_jsonl(media_item)

    @final
    async def handle_file(
        self,
        url: AbsoluteHttpURL,
        scrape_item: ScrapeItem,
        filename: str,
        ext: str | None = None,
        *,
        custom_filename: str | None = None,
        debrid_link: AbsoluteHttpURL | None = None,
        m3u8: m3u8.Rendition | None = None,
        metadata: object = None,
        referer: AbsoluteHttpURL | None = None,
    ) -> None:
        """Finishes handling the file and hands it off to the downloader."""

        ext = ext or Path(filename).suffix
        if self.DOMAIN in ["cyberdrop"]:
            custom_filename = remove_file_id(filename, ext)

        download_folder = get_download_path(self.manager, scrape_item, self.FOLDER_DOMAIN)
        media_item = MediaItem.from_item(
            scrape_item,
            url,
            self.DOMAIN,
            filename=custom_filename or filename,
            download_folder=download_folder,
            db_path=self.__db_path__(url),
            original_filename=filename,
            ext=ext,
        )
        media_item.debrid_link = debrid_link
        if metadata is not None:
            media_item.metadata = metadata
        if referer:
            media_item.referer = referer
        media_item.headers.update(self._prepare_headers(scrape_item))
        await self.handle_media_item(media_item, m3u8)

    def _prepare_headers(self, scrape_item: ScrapeItem) -> dict[str, str]:
        return {
            "User-Agent": self.manager.config.global_settings.general.user_agent,
            "Referer": str(scrape_item.url),
        }

    @final
    async def _download(self, media_item: MediaItem, m3u8: m3u8.Rendition | None) -> None:
        try:
            if SKIP_DOWNLOAD.get():
                return

            if m3u8:
                await self.downloader.download_hls(media_item, m3u8)
            else:
                await self.downloader.run(media_item)

        finally:
            await self.__write_to_jsonl(media_item)

    async def __write_to_jsonl(self, media_item: MediaItem) -> None:
        if not self.manager.config.settings.files.dump_json:
            return

        await self.manager.logs.write_jsonl([media_item.serialize()])

    @final
    async def check_complete(self, url: AbsoluteHttpURL, referer: AbsoluteHttpURL | None = None) -> bool:
        """Checks if this URL has been download before.

        This method is called automatically on a created media item,
        but Crawler code can use it to skip unnecessary requests"""

        db_path = self.__db_path__(url)
        current_referer, downloaded = await self.manager.database.history.check_complete(self.DOMAIN, db_path)
        if downloaded:
            logger.info("Skipping %s as it has already been downloaded", url)
            self.manager.scrape_mapper.tui.files.stats.previously_completed += 1

            if referer and url != referer and str(referer) != current_referer:
                # Update the referer if it has changed so that check_complete_by_referer can work
                logger.info("Updating referer of %s from %s to %s", url, current_referer, referer)
                await self.manager.database.history.update_referer(self.DOMAIN, db_path, referer)

        return downloaded

    async def handle_media_item(self, media_item: MediaItem, m3u8: m3u8.Rendition | None = None) -> None:
        if await self.check_complete(media_item.url, media_item.referer):
            if media_item.album_id:
                await self.manager.database.history.set_album_id(self.DOMAIN, media_item)
            return

        if await self.check_skip_by_config(media_item):
            self.manager.scrape_mapper.tui.files.stats.skipped += 1
            return

        self.manager.scrape_mapper.create_download_task(self._download(media_item, m3u8))

    @final
    async def check_skip_by_config(self, media_item: MediaItem) -> bool:
        media_host = media_item.url.host
        ignore_options = self.manager.config.settings.ignore_options

        if (hosts := ignore_options.skip_hosts) and any(host in media_host for host in hosts):
            logger.info(f"Download skipped {media_item.url} due to skip_hosts config")
            return True

        if (hosts := ignore_options.only_hosts) and not any(host in media_host for host in hosts):
            logger.info(f"Download skipped {media_item.url} due to only_hosts config")
            return True

        if (regex := ignore_options.filename_regex_filter) and re.search(regex, media_item.filename):
            logger.info(f"Download skipped {media_item.url} due to filename regex filter config")
            return True

        return False

    @final
    async def check_complete_from_referer(
        self: Crawler, scrape_item: ScrapeItem | AbsoluteHttpURL, any_crawler: bool = False
    ) -> bool:
        """Checks if the scrape item has already been scraped.

        if `any_crawler` is `True`, checks database entries for all crawlers and returns `True` if at least 1 of them has marked it as completed
        """
        url = _url(scrape_item)
        domain = None if any_crawler else self.DOMAIN
        downloaded = await self.manager.database.history.check_complete_by_referer(domain, url)
        if downloaded:
            logger.info(f"Skipping {url} as it has already been downloaded")
            self.manager.scrape_mapper.tui.files.stats.previously_completed += 1
        return downloaded

    @final
    async def check_complete_by_hash(
        self: Crawler, scrape_item: ScrapeItem | AbsoluteHttpURL, hash_type: Literal["md5", "sha256"], hash_value: str
    ) -> bool:
        """Returns `True` if at least 1 file with this hash is recorded on the database"""
        downloaded = await self.manager.database.hash.check_hash_exists(hash_type, hash_value)
        if downloaded:
            url = _url(scrape_item)
            logger.info(f"Skipping {url} as its hash ({hash_type}:{hash_value}) has already been downloaded")
            self.manager.scrape_mapper.tui.files.stats.previously_completed += 1
        return downloaded

    @final
    async def get_album_results(self, album_id: str) -> dict[str, bool]:
        """Checks whether an album has completed given its domain and album id."""
        return await self.manager.database.history.check_album(self.DOMAIN, album_id)

    @final
    def handle_external_links(self, scrape_item: ScrapeItem, reset: bool = True) -> None:
        """Maps external links to the scraper class."""
        if reset:
            scrape_item.reset()
        self.create_task(self.manager.scrape_mapper.send_to_crawler(scrape_item))

    @final
    def handle_embed(self, scrape_item: ScrapeItem) -> None:
        self.handle_external_links(scrape_item, reset=False)

    @final
    def get_filename_and_ext(
        self,
        filename: str,
        forum: bool = False,
        assume_ext: str | None = ".mp4",
        *,
        mime_type: str | None = None,
    ) -> tuple[str, str]:
        """Wrapper around `utils.get_filename_and_ext`.
        Calls it as is.
        If that fails, appends `assume_ext` and tries again, but only if the user had exclude_files_with_no_extension = `False`
        """
        try:
            return get_filename_and_ext(filename, mime_type, xenforo=forum)
        except NoExtensionError:
            if self.allow_no_extension and assume_ext:
                return get_filename_and_ext(filename + assume_ext, mime_type, xenforo=forum)
            raise

    @final
    def check_album_results(self, url: AbsoluteHttpURL, album_results: Mapping[str, bool]) -> bool:
        """Checks whether an album has completed given its domain and album id."""
        if not album_results:
            return False

        url_path = self.__db_path__(url)
        if album_results.get(url_path) is True:
            logger.info(f"Skipping {url} as it has already been downloaded")
            self.manager.scrape_mapper.tui.files.stats.previously_completed += 1
            return True
        return False

    @final
    def create_title(self, title: str, album_id: str | None = None, thread_id: int | None = None) -> str:
        """Creates the title for the scrape item."""
        title = (title or "Untitled").strip()

        if album_id and self.manager.config.settings.download_options.include_album_id_in_folder_name:
            title = f"{title} {album_id}"

        if thread_id and self.manager.config.settings.download_options.include_thread_id_in_folder_name:
            title = f"{title} {thread_id}"

        if not self.manager.config.settings.download_options.remove_domains_from_folder_names:
            title = f"{title} ({self.FOLDER_DOMAIN})"

        # Remove double spaces
        title = " ".join(title.split(" "))
        return title

    @final
    def create_separate_post_title(
        self,
        title: str | None = None,
        id: str | None = None,
        date: datetime.datetime | datetime.date | int | None = None,
        /,
    ) -> str:
        if not self.separate_posts:
            return ""
        title_format = self.manager.config.settings.download_options.separate_posts_format
        if title_format.strip().casefold() == "{default}":
            title_format = self.DEFAULT_POST_TITLE_FORMAT
        if isinstance(date, int):
            date = datetime.datetime.fromtimestamp(date)

        post_title, _ = safe_format(title_format, id=id, number=id, date=date, title=title)
        return post_title

    @classmethod
    def parse_url(
        cls,
        url: yarl.URL | str,
        /,
        relative_to: AbsoluteHttpURL | None = None,
        *,
        trim: bool | None = None,
    ) -> AbsoluteHttpURL:
        """Wrapper around `utils.parse_url` to use `self.PRIMARY_URL` as base"""
        base = relative_to or cls.PRIMARY_URL
        assert is_absolute_http_url(base)
        if trim is None:
            trim = cls.DEFAULT_TRIM_URLS
        return parse_url(url, base, trim=trim)

    @final
    def get_cookie_value(self, name: str) -> str | None:
        if morsel := self.client.client_manager.cookies.filter_cookies(self.PRIMARY_URL).get(name):
            return morsel.value

    @final
    def update_cookies(self, cookies: dict[str, Any], url: yarl.URL | None = None) -> None:
        """Update cookies for the provided URL

        If `url` is `None`, defaults to `self.PRIMARY_URL`
        """
        response_url = url or self.PRIMARY_URL
        self.client.client_manager.cookies.update_cookies(cookies, response_url)

    @final
    def iter_tags(
        self,
        soup: Tag,
        selector: str,
        /,
        attribute: str = "href",
        *,
        results: Mapping[str, bool] | None = None,
    ) -> Generator[tuple[AbsoluteHttpURL | None, AbsoluteHttpURL]]:
        """Generates tuples with an URL from the `src` value of the first image tag (AKA the thumbnail) and an URL from the value of `attribute`

        :param results: must be the output of `self.get_album_results`.
        If provided, it will be used as a filter, to only yield items that has not been downloaded before"""
        album_results = results or {}

        seen: set[str] = set()
        for tag in css.iselect(soup, selector):
            link_str: str | None = css.attr_or_none(tag, attribute)
            if not link_str or link_str in seen:
                continue
            seen.add(link_str)
            link = self.parse_url(link_str)
            if self.check_album_results(link, album_results):
                continue
            try:
                thumb_str: str | None = css.select(tag, "img", "src")
            except css.SelectorError:
                thumb = None
            else:
                thumb = None if is_blob_or_svg(thumb_str) else self.parse_url(thumb_str)

            yield thumb, link

    @final
    def iter_children(
        self,
        scrape_item: ScrapeItem,
        soup: BeautifulSoup,
        selector: str,
        /,
        attribute: str = "href",
        *,
        results: Mapping[str, bool] | None = None,
        **kwargs: Any,
    ) -> Generator[tuple[AbsoluteHttpURL | None, ScrapeItem]]:
        """Generates tuples with an URL from the `src` value of the first image tag (AKA the thumbnail) and a new scrape item from the value of `attribute`

        :param results: must be the output of `self.get_album_results`.
        If provided, it will be used as a filter, to only yield items that has not been downloaded before"""
        for thumb, link in self.iter_tags(soup, selector, attribute, results=results):
            new_scrape_item = scrape_item.create_child(link, **kwargs)
            yield thumb, new_scrape_item
            scrape_item.add_children()

    async def web_pager(
        self,
        url: AbsoluteHttpURL,
        selector: Callable[[BeautifulSoup], yarl.URL | str | None] | str | None = None,
        *,
        impersonate: BrowserTypeLiteral | bool | None = False,
        relative_to: AbsoluteHttpURL | None = None,
        trim: bool | None = None,
    ) -> AsyncIterator[BeautifulSoup]:
        """Generator of website pages"""

        relative_to = relative_to or url.origin()
        page_url = url
        if callable(selector):
            get_next_page = selector

        else:
            selector = selector or self.NEXT_PAGE_SELECTOR
            assert selector, f"No selector was provided and {self.DOMAIN} does define a next_page_selector"

            def get_next_page(soup: BeautifulSoup, /) -> yarl.URL | str | None:
                try:
                    return css.select(soup, selector, "href")
                except css.SelectorError:
                    return

        while True:
            soup = await self.request_soup(page_url, impersonate=impersonate or None)
            yield soup
            page_url_str = get_next_page(soup)
            if not page_url_str:
                break
            page_url = self.parse_url(page_url_str, relative_to=relative_to, trim=trim)

    @error_handling_wrapper
    async def direct_file(
        self, scrape_item: ScrapeItem, url: AbsoluteHttpURL | None = None, assume_ext: str | None = None
    ) -> None:
        """Download a direct link file. Filename will be the url slug"""
        link = url or scrape_item.url
        filename, ext = self.get_filename_and_ext(link.name or link.parent.name, assume_ext=assume_ext)
        await self.handle_file(link, scrape_item, filename, ext)

    @final
    @contextlib.asynccontextmanager
    async def new_task_group(self, scrape_item: ScrapeItem) -> AsyncGenerator[asyncio.TaskGroup]:
        async with asyncio.TaskGroup() as tg:
            with self.catch_errors(scrape_item):
                yield tg

    @final
    @classmethod
    def parse_date(cls, date_or_datetime: str, /, format: str) -> dates.TimeStamp | None:
        return dates.to_timestamp(dates.parse_format(date_or_datetime, format))

    @final
    @classmethod
    def parse_iso_date(cls, date_or_datetime: str, /) -> dates.TimeStamp | None:
        return dates.to_timestamp(dates.parse_iso(date_or_datetime))

    async def _get_redirect_url(self, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        async with self.request(url) as resp:
            return resp.url

    @final
    @error_handling_wrapper
    async def follow_redirect(self, scrape_item: ScrapeItem) -> None:
        redirect = await self._get_redirect_url(scrape_item.url)
        if scrape_item.url == redirect:
            raise ScrapeError(422, "Infinite redirect")
        scrape_item.url = redirect
        self.create_task(self.run(scrape_item))

    async def request_m3u8_playlist(
        self,
        m3u8_playlist_url: AbsoluteHttpURL,
        /,
        headers: Mapping[str, str] | None = None,
        *,
        only: Iterable[str] = (),
        exclude: Iterable[str] = ("vp09",),
    ) -> tuple[m3u8.Rendition, m3u8.RenditionDetails]:
        """Get m3u8 rendition group from a playlist m3u8 (variant m3u8), selecting the best format"""
        playlist, info = await self.request_m3u8(m3u8_playlist_url, headers, only=only, exclude=exclude)
        if info is None:
            raise ScrapeError(422, "Not a variant m3u8", origin=m3u8_playlist_url)
        return playlist, info

    @deprecated("Use self.request_m3u8 instead")
    async def get_m3u8_from_index_url(
        self, url: AbsoluteHttpURL, /, headers: Mapping[str, str] | None = None
    ) -> m3u8.Rendition:
        """Get m3u8 rendition group from an index that only has 1 rendition, a video (non variant m3u8)"""
        playlist, info = await self.request_m3u8(url, headers)
        if info is not None:
            raise ScrapeError(422, "This is a variant m3u8", origin=url)
        return playlist

    @deprecated("Use self._request_m3u8 instead")
    async def _get_m3u8(
        self,
        url: AbsoluteHttpURL,
        /,
        headers: Mapping[str, str] | None = None,
        media_type: Literal["video", "audio", "subtitle"] | None = None,
    ) -> m3u8.M3U8:
        return await self._request_m3u8(url, headers, media_type)

    @final
    def create_custom_filename(
        self,
        name: str,  # can be the full name or just the stem
        ext: str,
        /,
        *,
        file_id: str | None = None,
        video_codec: str | None = None,
        audio_codec: str | None = None,
        resolution: Resolution | str | int | None = None,
        fps: float | None = None,
        hash_string: str | None = None,
    ) -> str:

        def extra_info() -> Generator[str]:
            if _include.file_id and file_id:
                yield file_id
            if _include.video_codec and video_codec:
                yield video_codec
            if _include.audio_codec and audio_codec:
                yield audio_codec

            if _include.resolution and resolution and resolution not in (Resolution.highest(), Resolution.unknown()):
                res = resolution if type(resolution) is Resolution else Resolution.parse(resolution)
                if fps and _include.fps:
                    yield res.name + "@" + (str(int(fps)) if fps.is_integer() else f"{fps:.1f}") + "fps"
                else:
                    yield res.name

            if _include.hash and hash_string:
                assert any(hash_string.startswith(x) for x in _HASH_PREFIXES), f"Invalid: {hash_string = }"
                yield hash_string

        return compose_filename(name, ext, *extra_info())

    @final
    def handle_subs(self, scrape_item: ScrapeItem, video_filename: str, subtitles: Iterable[ISO639Subtitle]) -> None:
        counter = Counter()
        video_stem = Path(video_filename).stem
        for sub in subtitles:
            link = self.parse_url(sub.url)
            counter[sub.lang_code] += 1
            if (count := counter[sub.lang_code]) > 1:
                suffix = f"{sub.lang_code}.{count}{link.suffix}"
            else:
                suffix = f"{sub.lang_code}{link.suffix}"

            sub_name, ext = self.get_filename_and_ext(f"{video_stem}.{suffix}")
            new_scrape_item = scrape_item.create_new(scrape_item.url.with_fragment(sub_name))
            self.create_task(
                self.handle_file(
                    link,
                    new_scrape_item,
                    sub.name or link.name,
                    ext,
                    custom_filename=sub_name,
                )
            )


def _make_scrape_mapper_keys(cls: type[Crawler] | Crawler) -> tuple[str, ...]:
    hosts = cls.SUPPORTED_DOMAINS or cls.DOMAIN
    if isinstance(hosts, str):
        hosts = (hosts,)
    return tuple(sorted({host.removeprefix("www.") for host in hosts}))


def _validate_supported_paths(cls: type[Crawler]) -> None:
    for path_name, paths in cls.SUPPORTED_PATHS.items():
        assert path_name, f"{cls.__name__}, Invalid path: {path_name}"
        assert isinstance(paths, str | tuple), f"{cls.__name__}, Invalid path {path_name}: {type(paths)}"
        if path_name != "Direct links":
            assert paths, f"{cls.__name__} has not paths for {path_name}"

        if path_name.startswith("*"):  # note
            continue

        if isinstance(paths, str):
            paths = (paths,)

        for path in paths:
            assert "`" not in path, f"{cls.__name__}, Invalid path {path_name}: {path}"


def _make_wiki_supported_domains(scrape_mapper_keys: tuple[str, ...]) -> tuple[str, ...]:
    def generalize(domain):
        if "." not in domain:
            return f"{domain}.*"
        return domain

    return tuple(sorted(generalize(domain) for domain in scrape_mapper_keys))


def _sort_supported_paths(supported_paths: SupportedPaths) -> dict[str, OneOrTuple[str]]:
    def try_sort(value: OneOrTuple[str]) -> OneOrTuple[str]:
        if isinstance(value, tuple):
            return tuple(sorted(value))
        return value

    path_pairs = ((key, try_sort(value)) for key, value in supported_paths.items())
    return dict(sorted(path_pairs, key=lambda x: x[0].casefold()))


_CrawlerT = TypeVar("_CrawlerT", bound=Crawler)


def auto_task_id(
    func: Callable[Concatenate[_CrawlerT, ScrapeItem, _P], Coroutine[None, None, _R]],
) -> Callable[Concatenate[_CrawlerT, ScrapeItem, _P], Coroutine[None, None, _R]]:
    """Autocreate a new `task_id` from the scrape_item of the method"""

    @wraps(func)
    async def wrapper(self: _CrawlerT, scrape_item: ScrapeItem, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        with self.new_task_id(scrape_item.url):
            return await func(self, scrape_item, *args, **kwargs)

    return wrapper
