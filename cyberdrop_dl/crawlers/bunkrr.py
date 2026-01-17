from __future__ import annotations

import base64
import dataclasses
import itertools
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from aiohttp import ClientConnectorError

from cyberdrop_dl.constants import FILE_FORMATS
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths, auto_task_id
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import DDOSGuardError, ScrapeError
from cyberdrop_dl.utils import aio, css, open_graph
from cyberdrop_dl.utils.utilities import error_handling_wrapper, parse_url, xor_decrypt

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from bs4 import BeautifulSoup, Tag

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem
    from cyberdrop_dl.utils.aio import WeakAsyncLocks


_DOWNLOAD_API_ENTRYPOINT = AbsoluteHttpURL("https://apidl.bunkr.ru/api/_001_v2")
_STREAMING_API_ENTRYPOINT = AbsoluteHttpURL("https://bunkr.site/api/vs")
_PRIMARY_URL = AbsoluteHttpURL("https://bunkr.site")
_REINFORCED_URL_BASE = AbsoluteHttpURL("https://get.bunkrr.su")


class Selector:
    ALBUM_ITEM = "div.theItem"
    FILE_NAME = "p.theName"
    FILE_DATE = "span.theDate"
    DOWNLOAD_BUTTON = "a.btn.ic-download-01"
    FILE_THUMBNAIL = 'img[alt="image"]'
    IMAGE_PREVIEW = "img.max-h-full.w-auto.object-cover.relative"
    VIDEO = "video > source"
    NEXT_PAGE = "nav.pagination a[href]:-soup-contains('»')"


VIDEO_AND_IMAGE_EXTS: set[str] = FILE_FORMATS["Images"] | FILE_FORMATS["Videos"]
HOST_OPTIONS: set[str] = {"bunkr.site", "bunkr.cr", "bunkr.ph"}
known_bad_hosts: set[str] = set()


@dataclasses.dataclass(slots=True, frozen=True)
class ApiResponse:
    encrypted: bool
    timestamp: int
    url: str

    def decrypt(self: ApiResponse) -> str:
        if not self.encrypted:
            return self.url

        time_key = int(self.timestamp / 3600)
        secret_key = f"SECRET_KEY_{time_key}"
        encrypted_url = base64.b64decode(self.url)
        return xor_decrypt(encrypted_url, secret_key.encode())


@dataclasses.dataclass(slots=True, frozen=True)
class File:
    name: str
    thumbnail: str
    date: str
    path_qs: str

    @staticmethod
    def parse(tag: Tag) -> File:
        return File(
            name=css.select_text(tag, Selector.FILE_NAME),
            thumbnail=css.select(tag, Selector.FILE_THUMBNAIL, "src"),
            date=css.select_text(tag, Selector.FILE_DATE),
            path_qs=css.select(tag, "a", "href"),
        )

    @property
    def src(self) -> AbsoluteHttpURL:
        src_str = self.thumbnail.replace("/thumbs/", "/")
        src = parse_url(src_str).with_suffix(self.suffix).with_query(None)
        if src.suffix.lower() not in FILE_FORMATS["Images"]:
            return src.with_host(src.host.replace("i-", ""))
        return src

    @property
    def suffix(self) -> str:
        return Path(self.name).suffix


class BunkrrCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "bunkr", "bunkrr"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/a/<album_id>",
        "Video": "/v/<slug>",
        "File": (
            "/f/<slug>",
            "/<slug>",
        ),
        "Direct links": "",
    }

    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://bunkr.site")
    DATABASE_PRIMARY_HOST: ClassVar[str] = PRIMARY_URL.host
    DOMAIN: ClassVar[str] = "bunkrr"
    _RATE_LIMIT: ClassVar[tuple[float, float]] = 5, 1
    _USE_DOWNLOAD_SERVERS_LOCKS: ClassVar[bool] = True

    def __post_init__(self) -> None:
        self.switch_host_locks: WeakAsyncLocks[str] = aio.WeakAsyncLocks[str]()
        self.known_good_url: AbsoluteHttpURL | None = None

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["file", id_] if scrape_item.url.host == _REINFORCED_URL_BASE.host:
                return await self.reinforced_file(scrape_item, id_)
            case ["a", album_id]:
                return await self.album(scrape_item, album_id)
            case ["v", _]:
                return await self.follow_redirect(scrape_item)
            case ["f", slug]:
                return await self.file(scrape_item, slug)
            case [slug]:
                if _is_stream_redirect(scrape_item.url):
                    return await self.follow_redirect(scrape_item)

                if self.is_subdomain(scrape_item.url):
                    return await self.handle_direct_link(scrape_item, scrape_item.url)

                await self.file(scrape_item, slug)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        title: str = ""
        results = await self.get_album_results(album_id)
        seen: set[str] = set()
        stuck_in_a_loop_msg = f"Found duplicate URLs processing {scrape_item.url}. Aborting to prevent infinite loop"

        async for soup in self.web_pager(scrape_item.url):
            if not title:
                name = css.page_title(soup, "bunkr")
                title = self.create_title(name, album_id)
                scrape_item.setup_as_album(title, album_id=album_id)

            for tag in soup.select(Selector.ALBUM_ITEM):
                file = File.parse(tag)
                if file.path_qs in seen:
                    self.log(stuck_in_a_loop_msg, 40, bug=True)
                    return

                seen.add(file.path_qs)
                link = self.parse_url(file.path_qs, relative_to=scrape_item.url.origin())
                new_scrape_item = scrape_item.create_child(link)
                new_scrape_item.possible_datetime = self.parse_date(file.date, "%H:%M:%S %d/%m/%Y")
                self.create_task(self._album_file(new_scrape_item, file, results))
                scrape_item.add_children()

    async def web_pager(
        self,
        url: AbsoluteHttpURL,
        next_page_selector: str | None = None,
        *,
        cffi: bool = False,
        **kwargs: Any,
    ) -> AsyncGenerator[BeautifulSoup]:
        init_page = int(url.query.get("page") or 1)
        for page in itertools.count(init_page):
            soup = await self.request_soup_lenient(url.with_query(page=page))
            yield soup
            has_next_page = soup.select_one(Selector.NEXT_PAGE)
            if not has_next_page:
                break

    @auto_task_id
    @error_handling_wrapper
    async def _album_file(self, scrape_item: ScrapeItem, file: File, results: dict[str, int]) -> None:
        link = file.src
        if link.suffix.lower() not in VIDEO_AND_IMAGE_EXTS or "no-image" in link.name or self.deep_scrape:
            self.create_task(self.run(scrape_item))
            return

        if self.check_album_results(link, results):
            return

        await self.handle_direct_link(scrape_item, link, file.name)

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, slug: str) -> None:
        link: AbsoluteHttpURL | None = None
        db_url = scrape_item.url.with_host(self.DATABASE_PRIMARY_HOST)
        if await self.check_complete_from_referer(db_url):
            return

        soup = await self.request_soup_lenient(scrape_item.url)

        # Try image first to not make any additional request
        if image := soup.select_one(Selector.IMAGE_PREVIEW):
            link = self.parse_url(css.get_attr(image, "src"))

        # Try to get download URL from streaming API. Should work for most files, even none video files
        if not link:
            try:
                link = await self._request_download(slug=slug)
            except Exception:
                pass

        if not link and (dl_button := soup.select_one(Selector.DOWNLOAD_BUTTON)):
            id_ = self.parse_url(css.get_attr(dl_button, "href")).name
            link = await self._request_download(id_=id_)

        # Everything failed, abort
        if not link:
            raise ScrapeError(422, "Could not find source")

        title = open_graph.title(soup)  # See: https://github.com/jbsparrow/CyberDropDownloader/issues/929
        await self.handle_direct_link(scrape_item, link, fallback_filename=title)

    @error_handling_wrapper
    async def reinforced_file(self, scrape_item: ScrapeItem, id_: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        title = css.select_text(soup, "h1")
        link = await self._request_download(id_=id_)
        await self.handle_direct_link(scrape_item, link, fallback_filename=title)

    @error_handling_wrapper
    async def handle_direct_link(
        self, scrape_item: ScrapeItem, url: AbsoluteHttpURL, fallback_filename: str = ""
    ) -> None:
        """Handles direct links (CDNs URLs) before sending them to the downloader.

        `fallback_filename` will only be used if the link has no `n` query parameter"""

        link = url
        name = link.query.get("n") or fallback_filename or link.name
        link = link.update_query(n=name)
        filename, ext = self.get_filename_and_ext(name, assume_ext=".mp4")
        if not self.is_subdomain(scrape_item.url):
            scrape_item.url = scrape_item.url.with_host(self.DATABASE_PRIMARY_HOST)
        await self.handle_file(link, scrape_item, name, ext, custom_filename=filename)

    async def _request_download(self, *, id_: str = "", slug: str = "") -> AbsoluteHttpURL:
        """Gets the download link for a given URL

        1. Reinforced URL (get.bunkr.su/file/<file_id>). or
        2. Streaming URL (bunkr.site/f/<file_slug>)"""

        if id_:
            payload = {"id": id_}
            api_url = _DOWNLOAD_API_ENTRYPOINT

        else:
            payload = {"slug": slug.encode().decode("unicode-escape")}
            api_url = _STREAMING_API_ENTRYPOINT
            if self.known_good_url:
                api_url = _STREAMING_API_ENTRYPOINT.with_host(self.known_good_url.host)

        resp: dict[str, Any] = await self.request_json(
            api_url,
            "POST",
            json=payload,
            headers={"Referer": str(_REINFORCED_URL_BASE)},
        )
        return self.parse_url(ApiResponse(**resp).decrypt())

    async def _try_request_soup(self, url: AbsoluteHttpURL) -> BeautifulSoup | None:
        try:
            async with self.request(url) as resp:
                soup = await resp.soup()

        except (ClientConnectorError, DDOSGuardError):
            known_bad_hosts.add(url.host)
            if not HOST_OPTIONS - known_bad_hosts:
                raise
        else:
            if not self.known_good_url:
                self.known_good_url = resp.url.origin()
            return soup

    async def request_soup_lenient(self, url: AbsoluteHttpURL) -> BeautifulSoup:
        """Request soup with re-trying logic to use multiple hosts.

        We retry with a new host until we find one that's not DNS blocked nor DDoS-Guard protected

        If we find one, keep a reference to it and use it for all future requests"""

        if self.known_good_url:
            return await self.request_soup(url.with_host(self.known_good_url.host))

        async with self.switch_host_locks[url.host]:
            if url.host not in known_bad_hosts:
                if soup := await self._try_request_soup(url):
                    return soup

        for host in HOST_OPTIONS - known_bad_hosts:
            async with self.switch_host_locks[host]:
                if host in known_bad_hosts:
                    continue

                if soup := await self._try_request_soup(url.with_host(host)):
                    return soup

        # everything failed, do the request with the original URL to throw an exception
        return await self.request_soup(url)


def _is_stream_redirect(url: AbsoluteHttpURL) -> bool:
    first_subdomain = url.host.split(".")[0]
    prefix, _, number = first_subdomain.partition("cdn")
    if not prefix and number.isdigit():
        return True
    return any(part in url.host for part in ("cdn12", "cdn-")) or url.host == "cdn.bunkr.ru"
