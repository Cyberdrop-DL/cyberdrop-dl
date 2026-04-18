from __future__ import annotations

import base64
import dataclasses
import json
import re
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from aiohttp import ClientConnectorError

from cyberdrop_dl.constants import FILE_FORMATS
from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths, auto_task_id
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import DDOSGuardError, ScrapeError
from cyberdrop_dl.utils import aio, css, open_graph
from cyberdrop_dl.utils.utilities import error_handling_wrapper, parse_url, xor_decrypt

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


_DOWNLOAD_API_ENTRYPOINT = AbsoluteHttpURL("https://bunkr.cr/api/vs")
_DOWNLOAD_API_ENTRYPOINT_BY_ID = AbsoluteHttpURL("https://apidl.bunkr.ru/api/_001_v2")
_REINFORCED_URL = AbsoluteHttpURL("https://get.bunkrr.su")


class Selector:
    ALBUM_FILES = "script:-soup-contains('window.albumFiles = ')"
    ALBUM_PAGE_LINKS = "a[href*='page=']"
    DOWNLOAD_BUTTON = "a.btn.ic-download-01"
    IMAGE_PREVIEW = "img.max-h-full.w-auto.object-cover.relative"


VIDEO_AND_IMAGE_EXTS: set[str] = FILE_FORMATS["Images"] | FILE_FORMATS["Videos"]
HOST_OPTIONS: set[str] = {"bunkr.site", "bunkr.cr", "bunkr.ph"}
DEEP_SCRAPE_CDNS: set[str] = {"burger", "milkshake"}  # CDNs under maintanance, ignore them and try to get a cached URL
FILE_KEYS = "id", "name", "original", "slug", "type", "extension", "size", "timestamp", "thumbnail", "cdnEndpoint"
ALBUM_PAGE_CONCURRENCY = 5
known_bad_hosts: set[str] = set()


def _make_album_parser(keys: tuple[str, ...]) -> Callable[[BeautifulSoup], Generator[File]]:
    translation_map = {f" {key}: ": f'"{key}": ' for key in keys}
    pattern = re.compile("|".join(sorted(translation_map.keys(), key=len, reverse=True)))

    def fix_unicode(value: str) -> str:
        return value.encode("raw_unicode_escape").decode("unicode-escape")

    def decode(text: str) -> Generator[File]:
        content = pattern.sub(lambda m: translation_map[m.group(0)], text.replace("\\'", "'"))

        for file in json.loads(content):
            yield File(
                name=fix_unicode(file.get("original") or file["name"]),
                slug=fix_unicode(file["slug"]),
                thumbnail=fix_unicode(file["thumbnail"]),
                date=file["timestamp"],
            )

    def parse(soup: BeautifulSoup) -> Generator[File]:
        album_js = css.select_text(soup, Selector.ALBUM_FILES)
        files = album_js[album_js.find("=") + 1 : album_js.rfind("];") + 1]
        return decode(files)

    return parse


def _get_download_button_details(
    soup: BeautifulSoup,
    parse_url: Callable[[str, AbsoluteHttpURL | None], AbsoluteHttpURL],
    relative_to: AbsoluteHttpURL,
) -> tuple[str | None, AbsoluteHttpURL | None]:
    button = css.select(soup, Selector.DOWNLOAD_BUTTON)
    if file_id := css.get_attr_or_none(button, "data-id"):
        return file_id, None

    href = css.get_attr_or_none(button, "href")
    if not href:
        raise ScrapeError(422, "Bunkr download button is missing href")
    return None, parse_url(href, relative_to)


def _album_page_url(url: AbsoluteHttpURL, page: int) -> AbsoluteHttpURL:
    url = url.without_query_params("advanced", "page").update_query(advanced=1)
    if page > 1:
        return url.update_query(page=page)
    return url


def _get_album_last_page(
    soup: BeautifulSoup,
    parse_url: Callable[[str, AbsoluteHttpURL | None], AbsoluteHttpURL],
    relative_to: AbsoluteHttpURL,
) -> int | None:
    last_page = None
    for page_link in css.iselect(soup, Selector.ALBUM_PAGE_LINKS):
        href = css.get_attr_or_none(page_link, "href")
        if not href:
            continue

        page_url = parse_url(href, relative_to)
        if page_url.parts[1:3] != relative_to.parts[1:3]:
            continue

        page = page_url.query.get("page")
        try:
            page_num = int(page) if page else 1
        except ValueError:
            continue

        last_page = max(last_page or page_num, page_num)
    return last_page


@dataclasses.dataclass(slots=True, frozen=True)
class ApiResponse:
    encrypted: bool
    timestamp: int
    url: str

    def decrypt(self) -> str:
        if not self.encrypted:
            return self.url

        time_key = self.timestamp // 3600
        secret_key = f"SECRET_KEY_{time_key}"
        encrypted_url = base64.b64decode(self.url)
        return xor_decrypt(encrypted_url, secret_key.encode())


@dataclasses.dataclass(slots=True, frozen=True)
class File:
    name: str
    thumbnail: str
    date: str
    slug: str

    def src(self) -> AbsoluteHttpURL:
        if self.thumbnail.count("https://") != 1:
            raise ValueError
        if AbsoluteHttpURL(self.thumbnail).parts[1:2] != ("thumbs",):
            raise ValueError

        src_str = self.thumbnail.replace("/thumbs/", "/")
        ext = Path(self.name).suffix
        src = parse_url(src_str).with_suffix(ext).with_query(None)
        if src.suffix.lower() not in FILE_FORMATS["Images"]:
            src = src.with_host(src.host.replace("i-", ""))
        return _override_cdn(src)


class BunkrrCrawler(Crawler):
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
    DOMAIN: ClassVar[str] = "bunkr"
    _RATE_LIMIT: ClassVar[RateLimit] = 5, 1
    _USE_DOWNLOAD_SERVERS_LOCKS: ClassVar[bool] = True

    def __post_init__(self) -> None:
        self.switch_host_locks: aio.WeakAsyncLocks[str] = aio.WeakAsyncLocks()
        self.known_good_url: AbsoluteHttpURL | None = None
        self._parse_album_files = _make_album_parser(FILE_KEYS)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["file", file_id] if scrape_item.url.host == _REINFORCED_URL.host:
                return await self.reinforced_file(scrape_item, file_id)
            case ["a", album_id]:
                return await self.album(scrape_item, album_id)
            case ["v", _]:
                return await self.follow_redirect(scrape_item)
            case ["f", _]:
                return await self.file(scrape_item)
            case [_]:
                if _is_stream_redirect(scrape_item.url):
                    return await self.follow_redirect(scrape_item)

                if self.is_subdomain(scrape_item.url):
                    return await self._direct_file(scrape_item, scrape_item.url)

        raise ValueError

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        await self._album(scrape_item, album_id)

    async def _album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup = await self._request_soup_lenient(_album_page_url(scrape_item.url, 1))
        name = open_graph.title(soup)
        title = self.create_title(name, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        origin = scrape_item.url.origin()
        results = await self.get_album_results(album_id)
        seen_slugs: set[str] = set()
        last_page = _get_album_last_page(soup, self.parse_url, scrape_item.url)
        if not self._queue_album_page_files(scrape_item, origin, results, seen_slugs, soup):
            return

        if last_page is not None:
            await self._scrape_known_album_pages(
                scrape_item,
                origin,
                results,
                seen_slugs,
                start_page=2,
                last_page=last_page,
            )
            return

        await self._probe_album_pages(scrape_item, origin, results, seen_slugs, start_page=2)

    def _queue_album_page_files(
        self,
        scrape_item: ScrapeItem,
        origin: AbsoluteHttpURL,
        results: dict[str, int],
        seen_slugs: set[str],
        soup: BeautifulSoup,
    ) -> bool:
        found_new_file = False
        for file in self._parse_album_files(soup):
            if file.slug in seen_slugs:
                continue

            seen_slugs.add(file.slug)
            found_new_file = True
            web_url = origin / "f" / file.slug
            new_scrape_item = scrape_item.create_child(web_url)
            self.create_task(self._album_file(new_scrape_item, file, results))
            scrape_item.add_children()
        return found_new_file

    async def _scrape_known_album_pages(
        self,
        scrape_item: ScrapeItem,
        origin: AbsoluteHttpURL,
        results: dict[str, int],
        seen_slugs: set[str],
        *,
        start_page: int,
        last_page: int,
    ) -> None:
        page = start_page
        while page <= last_page:
            batch_last_page = min(last_page, page + ALBUM_PAGE_CONCURRENCY - 1)
            pages = list(range(page, batch_last_page + 1))
            page_urls = [_album_page_url(scrape_item.url, page_num) for page_num in pages]
            soups = await aio.gather(
                [self._request_soup_lenient(page_url) for page_url in page_urls],
                batch_size=ALBUM_PAGE_CONCURRENCY,
            )
            processed_until = pages[-1]

            for page_url, soup in zip(page_urls, soups, strict=True):
                if page_last_page := _get_album_last_page(soup, self.parse_url, page_url):
                    last_page = max(last_page, page_last_page)
                self._queue_album_page_files(scrape_item, origin, results, seen_slugs, soup)

            page = processed_until + 1

    async def _probe_album_pages(
        self,
        scrape_item: ScrapeItem,
        origin: AbsoluteHttpURL,
        results: dict[str, int],
        seen_slugs: set[str],
        *,
        start_page: int,
    ) -> None:
        page = start_page
        while True:
            page_url = _album_page_url(scrape_item.url, page)
            try:
                soup = await self._request_soup_lenient(page_url)
                page_last_page = _get_album_last_page(soup, self.parse_url, page_url)
                found_new_file = self._queue_album_page_files(scrape_item, origin, results, seen_slugs, soup)
            except ScrapeError:
                break

            if page_last_page and page < page_last_page:
                await self._scrape_known_album_pages(
                    scrape_item,
                    origin,
                    results,
                    seen_slugs,
                    start_page=page + 1,
                    last_page=page_last_page,
                )
                return

            if not found_new_file:
                break

            page += 1

    @auto_task_id
    @error_handling_wrapper
    async def _album_file(self, scrape_item: ScrapeItem, file: File, results: dict[str, int]) -> None:
        db_url = scrape_item.url.with_host(self.DATABASE_PRIMARY_HOST)
        scrape_item.possible_datetime = self.parse_date(file.date, "%H:%M:%S %d/%m/%Y")
        try:
            src = file.src()
        except ValueError:
            if await self.check_complete_from_referer(db_url):
                return
            self.create_task(self.run(scrape_item))
            return

        if self.check_album_results(src, results):
            return

        if await self.check_complete_from_referer(db_url):
            return

        deep_scrape = (
            src.suffix.lower() not in VIDEO_AND_IMAGE_EXTS
            or "no-image" in src.name
            or self.deep_scrape
            or any(cdn in src.host for cdn in DEEP_SCRAPE_CDNS)
        )
        if deep_scrape:
            self.create_task(self.run(scrape_item))
            return

        await self._direct_file(scrape_item, src, file.name)

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        db_url = scrape_item.url.with_host(self.DATABASE_PRIMARY_HOST)
        if await self.check_complete_from_referer(db_url):
            return

        soup = await self._request_soup_lenient(scrape_item.url)
        src = None
        if image := soup.select_one(Selector.IMAGE_PREVIEW):
            src = self.parse_url(css.get_attr(image, "src"))
            if len(src.parts) > 2:
                src = None

        if not src:
            src = await self._resolve_download_src(scrape_item, soup)

        name = open_graph.title(soup)  # See: https://github.com/jbsparrow/CyberDropDownloader/issues/929
        await self._direct_file(scrape_item, src, name)

    @error_handling_wrapper
    async def reinforced_file(self, scrape_item: ScrapeItem, file_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        name = css.select_text(soup, "h1")
        src = await self._resolve_download_src(scrape_item, soup)
        await self._direct_file(scrape_item, src, name)

    @error_handling_wrapper
    async def _direct_file(
        self, scrape_item: ScrapeItem, link: AbsoluteHttpURL, fallback_filename: str | None = None
    ) -> None:
        name = link.query.get("n") or fallback_filename or link.name
        link = link.update_query(n=name)
        filename, ext = self.get_filename_and_ext(name, assume_ext=".mp4")
        if not self.is_subdomain(scrape_item.url):
            scrape_item.url = scrape_item.url.with_host(self.DATABASE_PRIMARY_HOST)
        elif link.host == scrape_item.url.host:
            scrape_item.url = _REINFORCED_URL
        await self.handle_file(_override_cdn(link), scrape_item, name, ext, custom_filename=filename)

    async def _request_download(self, slug: str) -> AbsoluteHttpURL:
        resp: dict[str, Any] = await self.request_json(
            _DOWNLOAD_API_ENTRYPOINT,
            "POST",
            json={"slug": slug},
            headers={"Referer": "https://bunkr.sk/"},
        )
        return self.parse_url(ApiResponse(**resp).decrypt())

    async def _request_download_by_id(self, file_id: str) -> AbsoluteHttpURL:
        resp: dict[str, Any] = await self.request_json(
            _DOWNLOAD_API_ENTRYPOINT_BY_ID,
            "POST",
            json={"id": file_id},
        )
        return self.parse_url(ApiResponse(**resp).decrypt())

    async def _resolve_download_src(self, scrape_item: ScrapeItem, soup: BeautifulSoup) -> AbsoluteHttpURL:
        file_id, dl_link = _get_download_button_details(soup, self.parse_url, scrape_item.url.origin())
        if file_id:
            return await self._request_download_by_id(file_id)

        assert dl_link is not None
        if dl_link.host == _REINFORCED_URL.host and dl_link.parts[1:2] == ("file",):
            return await self._request_download_by_id(dl_link.name)

        # Some pages already expose a CDN URL directly; keep using it as-is.
        if dl_link.host not in HOST_OPTIONS and dl_link.host != self.DATABASE_PRIMARY_HOST:
            return dl_link

        return await self._request_download(dl_link.name)

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
            if url.query.get("advanced") and url.query != resp.url.query:
                soup = await self.request_soup(resp.url.with_query(url.query))
            return soup

    async def _request_soup_lenient(self, url: AbsoluteHttpURL) -> BeautifulSoup:
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


def _override_cdn(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    if "milkshake" in url.host:
        return url.with_host("mlk-bk.cdn.gigachad-cdn.ru")
    if "burger." in url.host:
        return url.with_host("brg-bk.cdn.gigachad-cdn.ru")
    return url
