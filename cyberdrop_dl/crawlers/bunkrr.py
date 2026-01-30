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
from cyberdrop_dl.exceptions import DDOSGuardError
from cyberdrop_dl.utils import aio, css, open_graph
from cyberdrop_dl.utils.utilities import error_handling_wrapper, parse_url, xor_decrypt

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


_DOWNLOAD_API_ENTRYPOINT = AbsoluteHttpURL("https://apidl.bunkr.ru/api/_001_v2")
_REINFORCED_URL = AbsoluteHttpURL("https://get.bunkrr.su")


class Selector:
    ALBUM_FILES = "script:-soup-contains('window.albumFiles = ')"
    DOWNLOAD_BUTTON = "a.btn.ic-download-01"
    IMAGE_PREVIEW = "img.max-h-full.w-auto.object-cover.relative"


VIDEO_AND_IMAGE_EXTS: set[str] = FILE_FORMATS["Images"] | FILE_FORMATS["Videos"]
HOST_OPTIONS: set[str] = {"bunkr.site", "bunkr.cr", "bunkr.ph"}
DEEP_SCRAPE_CDNS: set[str] = {"pizza", "wiener"}  # CDNs under maintanance, ignore them and try to get a cached URL
FILE_KEYS = "id", "name", "original", "slug", "type", "extension", "size", "timestamp", "thumbnail", "cdnEndpoint"
known_bad_hosts: set[str] = set()


def _make_album_parser(keys: tuple[str, ...]) -> Callable[[BeautifulSoup], Generator[File]]:
    translation_map = {f"{key}: ": f'"{key}": ' for key in keys}
    pattern = re.compile("|".join(sorted(translation_map, key=len, reverse=True)))

    def decode(text: str) -> Generator[File]:
        content = (
            pattern.sub(lambda m: translation_map[m.group(0)], text)
            .encode("raw_unicode_escape")
            .decode("unicode-escape")
        )

        for file in json.loads(content):
            yield File(
                name=file.get("original") or file["name"],
                slug=file["slug"],
                thumbnail=file["thumbnail"],
                date=file["timestamp"],
            )

    def parse(soup: BeautifulSoup) -> Generator[File]:
        album_js = css.select_text(soup, Selector.ALBUM_FILES)
        files = album_js[album_js.find("=") + 1 : album_js.rfind("];") + 1]
        return decode(files)

    return parse


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
        soup = await self._request_soup_lenient(scrape_item.url.with_query(advanced=1))
        name = open_graph.title(soup)
        title = self.create_title(name, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        origin = scrape_item.url.origin()
        results = await self.get_album_results(album_id)
        for file in self._parse_album_files(soup):
            web_url = origin / "f" / file.slug
            new_scrape_item = scrape_item.create_child(web_url)
            self.create_task(self._album_file(new_scrape_item, file, results))
            scrape_item.add_children()

    @auto_task_id
    @error_handling_wrapper
    async def _album_file(self, scrape_item: ScrapeItem, file: File, results: dict[str, int]) -> None:
        db_url = scrape_item.url.with_host(self.DATABASE_PRIMARY_HOST)
        if await self.check_complete_from_referer(db_url):
            return

        src = file.src()
        scrape_item.possible_datetime = self.parse_date(file.date, "%H:%M:%S %d/%m/%Y")
        if (
            src.suffix.lower() not in VIDEO_AND_IMAGE_EXTS
            or "no-image" in src.name
            or self.deep_scrape
            or any(cdn in src.host for cdn in DEEP_SCRAPE_CDNS)
        ):
            self.create_task(self.run(scrape_item))
            return

        if self.check_album_results(src, results):
            return

        await self._direct_file(scrape_item, src, file.name)

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        db_url = scrape_item.url.with_host(self.DATABASE_PRIMARY_HOST)
        if await self.check_complete_from_referer(db_url):
            return

        soup = await self._request_soup_lenient(scrape_item.url)
        if image := soup.select_one(Selector.IMAGE_PREVIEW):
            src = self.parse_url(css.get_attr(image, "src"))

        else:
            dl_link = css.select(soup, Selector.DOWNLOAD_BUTTON, "href")
            file_id = self.parse_url(dl_link).name
            src = await self._request_download(file_id)

        name = open_graph.title(soup)  # See: https://github.com/jbsparrow/CyberDropDownloader/issues/929
        await self._direct_file(scrape_item, src, name)

    @error_handling_wrapper
    async def reinforced_file(self, scrape_item: ScrapeItem, file_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        name = css.select_text(soup, "h1")
        src = await self._request_download(file_id)
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
        await self.handle_file(link, scrape_item, name, ext, custom_filename=filename)

    async def _request_download(self, file_id: str) -> AbsoluteHttpURL:
        resp: dict[str, Any] = await self.request_json(
            _DOWNLOAD_API_ENTRYPOINT,
            "POST",
            json={"id": file_id},
            headers={"Referer": str(_REINFORCED_URL)},
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
    return url
