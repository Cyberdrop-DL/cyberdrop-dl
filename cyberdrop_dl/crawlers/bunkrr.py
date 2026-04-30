from __future__ import annotations

import asyncio
import base64
import dataclasses
import json
import re
from collections.abc import Generator
from typing import TYPE_CHECKING, Any, ClassVar

from aiohttp import ClientConnectorError
from typing_extensions import override

from cyberdrop_dl.constants import FileExt
from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths, auto_task_id
from cyberdrop_dl.exceptions import DDOSGuardError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper, open_graph, parse_url, xor_decrypt

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


_DOWNLOAD_API_ENTRYPOINT = AbsoluteHttpURL("https://apidl.bunkr.ru/api/_001_v2")
_REINFORCED_URL = AbsoluteHttpURL("https://get.bunkrr.su")


class Selector:
    ALBUM_FILES = "script:-soup-contains('window.albumFiles = ')"
    DOWNLOAD_BTN = "a.btn.ic-download-01"
    SERVER_UNDER_MAINTENANCE = "h2:-soup-contains('Server under maintenance')"
    IMAGE_CONTAINER = "img.max-h-full.w-auto.object-cover.relative"


_HOST_OPTIONS: frozenset[str] = frozenset(("bunkr.site", "bunkr.cr", "bunkr.ph"))
_DEEP_SCRAPE_CDNS: frozenset[str] = frozenset(
    (
        "burger",
        "cheese",
        "kebab",
        "milkshake",
        "static.scdn.st",
        "wiener",
    )
)  # CDNs under maintenance, ignore them and try to get a cached URL

known_bad_hosts: set[str] = set()


def _make_album_parser() -> Callable[[str], Generator[File]]:
    translation_map = {f" {field.name}: ": f'"{field.name}": ' for field in dataclasses.fields(File)}
    pattern = re.compile("|".join(sorted(translation_map.keys(), key=len, reverse=True)))

    def translate(text: str) -> str:
        return pattern.sub(lambda m: translation_map[m.group(0)], text.replace("\\'", "'")).strip()

    def decode(content: str) -> Generator[File]:
        file: dict[str, Any]
        for file in json.loads(content):
            yield File(**file)

    def parse(album_js: str) -> Generator[File]:
        content = translate(album_js[album_js.find("=") + 1 : album_js.rfind("];")])
        return decode(content.rstrip(",") + "]")

    return parse


@dataclasses.dataclass(slots=True)
class File:
    id: int
    name: str
    original: str | None
    slug: str
    type: str
    extension: str
    size: int
    timestamp: str
    thumbnail: str
    cdnEndpoint: str  # noqa: N815

    src: AbsoluteHttpURL | None = dataclasses.field(compare=False, default=None)

    def __post_init__(self) -> None:
        if self.src:
            return

        if self.thumbnail.count("https://") != 1:
            return

        src = parse_url(self.thumbnail).with_path(self.cdnEndpoint)

        if src.suffix.lower() not in FileExt.IMAGE:
            src = src.with_host(src.host.replace("i-", ""))

        self.src = _override_cdn(src)


class BunkrrCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/a/<album_id>",
        "Video": "/v/<slug>",
        "File": (
            "/f/<slug>",
            "/d/<slug>",
            "/<slug>",
        ),
        "Direct links": "",
    }

    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://bunkr.site")
    DOMAIN: ClassVar[str] = "bunkr"
    _RATE_LIMIT: ClassVar[RateLimit] = 5, 1
    _USE_DOWNLOAD_SERVERS_LOCKS: ClassVar[bool] = True
    _known_good_host: ClassVar[str | None] = None

    def __post_init__(self) -> None:
        self._redirect_lock: asyncio.Lock = asyncio.Lock()
        self._parse_album_files = _make_album_parser()

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["file", file_id] if scrape_item.url.host == _REINFORCED_URL.host:
                return await self.reinforced_file(scrape_item, file_id)
            case ["a", album_id]:
                return await self.album(scrape_item, album_id)
            case ["v" | "d", _]:
                return await self.follow_redirect(scrape_item)
            case ["f", _]:
                return await self.file(scrape_item)
            case [_]:
                if _is_stream_redirect(scrape_item.url):
                    return await self.follow_redirect(scrape_item)

                if self.is_subdomain(scrape_item.url):
                    return await self._direct_file(scrape_item, scrape_item.url)

                raise ValueError
            case _:
                raise ValueError

    @override
    async def _get_redirect_url(self, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        if not self._known_good_host:
            async with self._redirect_lock:
                if not self._known_good_host:
                    _ = await self._request_soup_lenient(url)
        assert self._known_good_host
        return await super()._get_redirect_url(url.with_host(self._known_good_host))

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup = await self._request_soup_lenient(scrape_item.url.with_query(advanced=1))
        name = open_graph.title(soup)
        title = self.create_title(name, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        origin = scrape_item.url.origin()
        results = await self.get_album_results(album_id)
        for file in self._parse_album_files(css.select_text(soup, Selector.ALBUM_FILES)):
            web_url = origin / "f" / file.slug
            new_scrape_item = scrape_item.create_child(web_url)
            self.create_task(self._album_file(new_scrape_item, file, results))
            scrape_item.add_children()

    @auto_task_id
    @error_handling_wrapper
    async def _album_file(self, scrape_item: ScrapeItem, file: File, results: dict[str, bool]) -> None:
        db_url = scrape_item.url.with_host(self.PRIMARY_URL.host)
        if await self.check_complete_from_referer(db_url):
            return

        scrape_item.uploaded_at = self.parse_date(file.timestamp, "%H:%M:%S %d/%m/%Y")

        src = file.src
        if not src:
            self.create_task(self.run(scrape_item))
            return

        deep_scrape = (
            src.suffix.lower() not in FileExt.VIDEO_OR_IMAGE
            or "no-image" in src.name
            or self.deep_scrape
            or any(cdn in src.host for cdn in _DEEP_SCRAPE_CDNS)
        )

        if deep_scrape:
            self.create_task(self.run(scrape_item))
            return

        if self.check_album_results(src, results):
            return

        await self._direct_file(scrape_item, src, file.original or file.name)

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        db_url = scrape_item.url.with_host(self.PRIMARY_URL.host)
        if await self.check_complete_from_referer(db_url):
            return

        soup = await self._request_soup_lenient(scrape_item.url)
        src = None
        if soup.select_one(Selector.SERVER_UNDER_MAINTENANCE):
            raise ScrapeError("Bunkr Maintenance", message="Server under maintenance")

        try:
            image = self.parse_url(css.select(soup, Selector.IMAGE_CONTAINER, "src"))
        except css.SelectorError:
            pass
        else:
            if len(image.parts) == 2:
                src = image

        if self.deep_scrape or not src:
            reinforced_url = css.select(soup, Selector.DOWNLOAD_BTN, "href")
            referrer_url = self.parse_url(reinforced_url)
            file_id = referrer_url.name
            src = await self._request_download(file_id, referrer_url)

        await self._direct_file(scrape_item, src, open_graph.title(soup))

    @error_handling_wrapper
    async def reinforced_file(self, scrape_item: ScrapeItem, file_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        name = css.select_text(soup, "h1")
        src = await self._request_download(file_id, scrape_item.url)
        await self._direct_file(scrape_item, src, name)

    @error_handling_wrapper
    async def _direct_file(self, scrape_item: ScrapeItem, link: AbsoluteHttpURL, filename: str | None = None) -> None:
        name = link.query.get("n") or filename or link.name
        link = link.update_query(n=name)
        filename, ext = self.get_filename_and_ext(name, assume_ext=".mp4")
        if not self.is_subdomain(scrape_item.url):
            scrape_item.url = scrape_item.url.with_host(self.PRIMARY_URL.host)
        elif link.host == scrape_item.url.host:
            scrape_item.url = _REINFORCED_URL
        await self.handle_file(_override_cdn(link), scrape_item, name, ext, custom_filename=filename)

    async def _request_download(self, file_id: str, referrer: AbsoluteHttpURL) -> AbsoluteHttpURL:
        resp: dict[str, Any] = await self.request_json(
            _DOWNLOAD_API_ENTRYPOINT,
            "POST",
            json={"id": file_id},
            headers={"Referer": str(referrer)},
        )
        return self.parse_url(_parse_api_resp(**resp))

    async def _try_request_soup(self, url: AbsoluteHttpURL) -> BeautifulSoup | None:
        try:
            async with self.request(url) as resp:
                soup = await resp.soup()

        except (ClientConnectorError, DDOSGuardError):
            known_bad_hosts.add(url.host)
            if not _HOST_OPTIONS - known_bad_hosts:
                raise
        else:
            if not self._known_good_host:
                type(self)._known_good_host = resp.url.host
            if url.query.get("advanced") and url.query != resp.url.query:
                soup = await self.request_soup(resp.url.with_query(url.query))
            return soup

    async def _request_soup_lenient(self, url: AbsoluteHttpURL) -> BeautifulSoup:
        """Request soup with re-trying logic to use multiple hosts.

        We retry with a new host until we find one that's not DNS blocked nor DDoS-Guard protected

        If we find one, keep a reference to it and use it for all future requests"""

        if self._known_good_host:
            return await self.request_soup(url.with_host(self._known_good_host))

        async with self._startup_lock:
            if url.host not in known_bad_hosts:
                if soup := await self._try_request_soup(url):
                    return soup

            for host in _HOST_OPTIONS - known_bad_hosts:
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


def _parse_api_resp(url: str, timestamp: int, encrypted: bool) -> str:
    if not encrypted:
        return url

    time_key = timestamp // 3600
    secret_key = f"SECRET_KEY_{time_key}".encode()
    return xor_decrypt(base64.b64decode(url), secret_key)
