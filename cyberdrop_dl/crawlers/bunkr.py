from __future__ import annotations

import asyncio
import dataclasses
import json
import re
from typing import TYPE_CHECKING, Any, ClassVar

from aiohttp import ClientConnectorError
from typing_extensions import override

from cyberdrop_dl.crawlers.crawler import API, Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.exceptions import DDOSGuardError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, deserialize, error_handling_wrapper, open_graph, parse_url

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


_REINFORCED_URL = AbsoluteHttpURL("https://get.bunkrr.su/file")
_SIGN_API = AbsoluteHttpURL("https://glb-apisign.cdn.cr/sign")
_HOST_OPTIONS: frozenset[str] = frozenset(("bunkr.site", "bunkr.cr", "bunkr.ph"))
_find_js_vars = re.compile(r'var\s+(\w+)\s*=\s*(".*?"|\'.*?\'|[^;]+);', re.DOTALL).findall
known_bad_hosts: set[str] = set()


class Selector:
    ALBUM_FILES = "script:-soup-contains('window.albumFiles = ')"
    DOWNLOAD_BTN = "a.btn.ic-download-01"
    SERVER_UNDER_MAINTENANCE = "h2:-soup-contains('Server under maintenance')"
    JS_VARS = "script:-soup-contains-own('var jsCDN')"


class BunkrCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/a/<album_id>",
        "Video": "/v/<slug>",
        "File": (
            "/f/<slug>",
            "/d/<slug>",
            "/i/<slug>",
        ),
        "Stream redirect": "/<slug>",
    }

    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://bunkr.site")
    DOMAIN: ClassVar[str] = "bunkr"
    _RATE_LIMIT: ClassVar[RateLimit] = 5, 1
    _USE_DOWNLOAD_SERVERS_LOCKS: ClassVar[bool] = True
    _known_good_host: ClassVar[str | None] = None

    @staticmethod
    @override
    def __db_path__(url: AbsoluteHttpURL, /) -> str:
        return "/" + url.name

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["v" | "d" | "i", js_slug]:
                return url.origin() / "f" / js_slug
            case _:
                return url

    def __post_init__(self) -> None:
        self.api: BunkrAPI = BunkrAPI(self)
        self._parse_files = _make_album_parser()
        self._redirect_lock: asyncio.Lock = asyncio.Lock()

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["file", file_id] if scrape_item.url.host == _REINFORCED_URL.host:
                return await self.reinforced_file(scrape_item, file_id)
            case ["a", album_id]:
                return await self.album(scrape_item, album_id)
            case ["v" | "d" | "i", _]:
                return await self.follow_redirect(scrape_item)
            case ["f", _]:
                return await self.file(scrape_item)
            case [_] if _is_stream_redirect(scrape_item.url.host):
                return await self.follow_redirect(scrape_item)
            case _:
                raise ValueError

    @override
    async def _get_redirect_url(self, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        try:
            return await super()._get_redirect_url(url)
        except (ClientConnectorError, DDOSGuardError):
            if self.is_subdomain(url):
                raise

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
        for file in self._parse_files(css.select_text(soup, Selector.ALBUM_FILES)):
            web_url = origin / "f" / file.slug
            new_item = scrape_item.create_child(web_url)
            new_item.uploaded_at = self.parse_date(file.timestamp, "%H:%M:%S %d/%m/%Y")
            self.create_task(self.run(new_item))
            scrape_item.add_children()

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        db_url = scrape_item.url.with_host(self.PRIMARY_URL.host)
        if await self.check_complete_from_referer(db_url):
            return

        soup = await self._request_soup_lenient(scrape_item.url)
        if soup.select_one(Selector.SERVER_UNDER_MAINTENANCE):
            raise ScrapeError("Bunkr Maintenance", "Server under maintenance")

        filename = open_graph.title(soup)
        try:
            cdn = _extract_js_vars(soup)["jsCDN"]
        except css.SelectorError:
            reinforced_url = css.select(soup, Selector.DOWNLOAD_BTN, "href")
            file_id = self.parse_url(reinforced_url).name
            source = await self.api.source(file_id)
            src = source.url
        else:
            src = self.parse_url(cdn)

        await self._file(scrape_item, src, filename)

    @error_handling_wrapper
    async def reinforced_file(self, scrape_item: ScrapeItem, file_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return
        source = await self.api.source(file_id)
        await self._file(scrape_item, source.url, source.ogname)

    async def _file(self, scrape_item: ScrapeItem, src: AbsoluteHttpURL, filename: str | None = None) -> None:
        src = await self.api.sign(src)
        name = src.query.get("n") or filename or src.name
        src = src.update_query(n=name)
        filename, ext = self.get_filename_and_ext(name, assume_ext=".mp4")
        if not self.is_subdomain(scrape_item.url):
            scrape_item.url = scrape_item.url.with_host(self.PRIMARY_URL.host)
        await self.handle_file(src, scrape_item, name, ext, custom_filename=filename)

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
            if url.host not in known_bad_hosts and (soup := await self._try_request_soup(url)):
                return soup

            for host in _HOST_OPTIONS - known_bad_hosts:
                if soup := await self._try_request_soup(url.with_host(host)):
                    return soup

        # everything failed, do the request with the original URL to throw an exception
        return await self.request_soup(url)


class BunkrAPI(API):
    async def source(self, file_id: str) -> Source:
        reinforced_url = _REINFORCED_URL / file_id
        soup = await self.request_soup(reinforced_url)
        js_vars = _extract_js_vars(soup)
        return deserialize(Source, js_vars)

    async def sign(self, src: AbsoluteHttpURL) -> AbsoluteHttpURL:
        api_url = _SIGN_API.with_query(path=src.path)
        resp = await self.request_json(api_url)
        return src.with_query(token=resp["token"], ex=resp["ex"])


@dataclasses.dataclass(slots=True)
class Source:
    ogname: str
    jsCDN: str  # noqa: N815
    jsType: str  # noqa: N815
    jsSlug: str  # noqa: N815
    signUrl: str  # noqa: N815
    url: AbsoluteHttpURL = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        self.url = parse_url(self.jsCDN) / "storage/media" / self.jsSlug


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


def _is_stream_redirect(host: str) -> bool:
    first_subdomain = host.split(".", maxsplit=1)[0]
    prefix, _, number = first_subdomain.partition("cdn")
    if not prefix and number.isdigit():
        return True
    return any(part in host for part in ("cdn12", "cdn-")) or host == "cdn.bunkr.ru"


def _extract_js_vars(soup: BeautifulSoup) -> dict[str, str]:
    script = css.select_text(soup, Selector.JS_VARS)
    return {k: _fix_encoding(v).strip("\"'") for k, v in _find_js_vars(script)}


def _fix_encoding(val: str) -> str:
    return val.replace(r"\/", "/")


def fix_db_referer(referer: str) -> str:
    url = AbsoluteHttpURL(referer)
    if BunkrCrawler.is_subdomain(url):
        return str(url)

    return str(BunkrCrawler.transform_url(url).with_host(BunkrCrawler.PRIMARY_URL.host))
