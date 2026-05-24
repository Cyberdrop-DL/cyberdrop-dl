from __future__ import annotations

import asyncio
import dataclasses
import json
import re
import struct
from collections import defaultdict
from datetime import timedelta
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import DictDataclass, error_handling_wrapper
from cyberdrop_dl.utils.filepath import get_filename_and_ext

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from cyberdrop_dl.url_objects import ScrapeItem


ALLOW_AVIF = False

_GALLERY_PARTS = "cg", "doujinshi", "galleries", "gamecg", "imageset", "manga", "reader", "anime"
_COLLECTION_PARTS = "artist", "character", "group", "series", "tag", "type"
_CONTENT_HOST = "gold-usergeneratedcontent.net"
_LTN_SERVER = AbsoluteHttpURL(f"https://ltn.{_CONTENT_HOST}/")
_PRIMARY_URL = AbsoluteHttpURL("https://hitomi.la")
_VIDEOS_SERVER = AbsoluteHttpURL(f"https://streaming.{_CONTENT_HOST}/")


class HitomiLaCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Gallery": tuple(f"/{g}/<slug>" for g in _GALLERY_PARTS),
        "Collection": tuple(f"/{g}/<slug>" for g in _COLLECTION_PARTS),
        "Search": "/search.html?<query>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = _PRIMARY_URL
    DOMAIN: ClassVar[str] = "hitomi.la"
    _RATE_LIMIT: ClassVar[tuple[float, float]] = 3, 1

    def __post_init__(self) -> None:
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(3)
        self.api: HitomiAPI = HitomiAPI(self)
        self.api.servers = aio.cached(self.api.servers)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [part, slug]:
                if part in _GALLERY_PARTS:
                    gallery_id = slug.split("-")[-1].removesuffix(".html")
                    return await self.gallery(scrape_item, gallery_id)
                if part in _COLLECTION_PARTS:
                    return await self.collection(scrape_item, part)
                raise ValueError
            case ["search.html"] if scrape_item.url.query:
                return await self.search(scrape_item, scrape_item.url.query_string)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def collection(self, scrape_item: ScrapeItem, colletion_type: str) -> None:
        name, _, language = scrape_item.url.name.removesuffix(".html").partition("-")

        if name == "index":
            title = f"{name} [{language}]"
            nozomi_url = _LTN_SERVER / f"{name}-{language}.nozomi"
        else:
            title = f"{name} [{colletion_type}][{language}]"
            nozomi_url = _LTN_SERVER / colletion_type / f"{name}-{language}.nozomi"

        scrape_item.setup_as_profile(self.create_title(title))
        sets = await self.api.nozomi(nozomi_url)
        await self._iter_galleries(scrape_item, sets)

    async def _iter_galleries(self, scrape_item: ScrapeItem, sets: Iterable[int]) -> None:
        for idx, gallery_id in enumerate(sets, 1):
            new_item = scrape_item.create_child(self.PRIMARY_URL / f"galleries/{gallery_id}.html")
            self.create_task(self.run(new_item))
            scrape_item.add_children()
            if idx % 300:
                await asyncio.sleep(0)

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, search_query: str) -> None:
        scrape_item.setup_as_profile(self.create_title(f"{search_query} [search]"))
        sets = await self.api.search(search_query)
        if not sets:
            raise ScrapeError(204)

        await self._iter_galleries(scrape_item, sets)

    @error_handling_wrapper
    async def gallery(self, scrape_item: ScrapeItem, gallery_id: str) -> None:
        gallery = await self.api.gallery(gallery_id)

        scrape_item.url = self.PRIMARY_URL / "galleries" / gallery_id
        title = self.create_title(f"{gallery.title} [{gallery.type}]", gallery.id)
        scrape_item.setup_as_album(title, album_id=gallery.id)
        scrape_item.uploaded_at = self.parse_iso_date(gallery.datepublished or gallery.date)
        await self._gallery(scrape_item, gallery)

    async def _gallery(self, scrape_item: ScrapeItem, gallery: Gallery) -> None:
        servers = await self.api.servers()
        reader_url = self.PRIMARY_URL / f"reader/{gallery.id}.html"
        results = await self.get_album_results(gallery.id)
        await self._video(scrape_item, gallery)

        for idx, image in enumerate(gallery.files, 1):
            web_url = reader_url.with_fragment(str(idx))
            if self.check_album_results(web_url, results):
                continue

            src = _build_src_url(servers, image)
            filename, ext = self.get_filename_and_ext(image.name)
            custom_filename = self.create_custom_filename(filename, src.suffix)
            await self.handle_file(
                web_url,
                scrape_item,
                filename,
                ext,
                custom_filename=custom_filename,
                debrid_link=src,
                referer=web_url,
            )
            scrape_item.add_children()

    @error_handling_wrapper
    async def _video(self, scrape_item: ScrapeItem, gallery: Gallery) -> None:
        if not gallery.videofilename:
            return

        src = _VIDEOS_SERVER / "videos" / gallery.videofilename
        await self.direct_file(scrape_item, src)
        scrape_item.add_children()


class Servers(defaultdict[int, int]):
    _EXPIRES_AFTER: ClassVar[timedelta] = timedelta(minutes=40)

    def __init__(self, root: int, default: int | None = None) -> None:
        if default is None:
            default = 0
        super().__init__(lambda: default)
        self.root: int = root


@dataclasses.dataclass(slots=True)
class SearchArgs:
    area: str | None
    tag: str
    language: str = "all"

    @property
    def url(self) -> AbsoluteHttpURL:
        name = f"{self.tag}-{self.language}.nozomi"
        if self.area:
            return _LTN_SERVER / "n" / self.area / name
        return _LTN_SERVER / "n" / name


@dataclasses.dataclass(slots=True)
class Image(DictDataclass):
    hash: str
    name: str
    hasavif: int


@dataclasses.dataclass(slots=True)
class Gallery(DictDataclass):
    blocked: int
    id: str
    title: str
    files: list[Image]
    type: str
    date: str
    datepublished: str | None = None
    videofilename: str | None = None


class HitomiAPI(API):
    headers: ClassVar[Mapping[str, str]] = {"Referer": str(_PRIMARY_URL), "Origin": str(_PRIMARY_URL)}

    async def servers(self) -> Servers:
        # https://ltn.gold-usergeneratedcontent.net/gg.js
        gg_url = _LTN_SERVER / "gg.js"
        js_text = await self.request_text(gg_url)
        return _decode_servers(js_text)

    async def gallery(self, gallery_id: str) -> Gallery:
        url = _LTN_SERVER / f"galleries/{gallery_id}.js"
        js_text = await self.request_text(url, headers=self.headers)
        gallery = Gallery.from_dict(json.loads(js_text.split("=", 1)[-1]))
        if gallery.blocked:
            raise ScrapeError(403)
        return gallery

    async def search(self, search_query: str) -> list[int]:
        # https://ltn.gold-usergeneratedcontent.net/search.js
        # This is partial implementation. Only parses tagged words, ex `female:dark_skin`
        # Free form query searches are ignored
        search_args = tuple(_parse_search_query(word) for word in search_query.split(" ") if ":" in word)
        first, *rest = await aio.map(self.nozomi, (a.url for a in search_args), task_limit=None)
        return sorted(set(first).intersection(*rest), reverse=True)

    async def nozomi(self, url: AbsoluteHttpURL) -> tuple[int, ...]:
        async with self.request(url, headers=self.headers) as response:
            content = await response.read()

        return _decode_nozomi_resp(content)


def _build_src_url(servers: Servers, image: Image) -> AbsoluteHttpURL:
    ext = "avif" if ALLOW_AVIF and image.hasavif else "webp"
    return _url_from_hash(servers, image, ext, ext=f".{ext}")


def _url_from_hash(servers: Servers, image: Image, dir_: str, ext: str | None = None) -> AbsoluteHttpURL:
    # https://ltn.gold-usergeneratedcontent.net/common.js
    ext = ext or get_filename_and_ext(image.name)[1]

    server_hex_num = int(image.hash[-1] + image.hash[-3:-1], base=16)
    server_num = servers[server_hex_num] + 1
    origin = AbsoluteHttpURL(f"https://{ext[1]}{server_num}.{_CONTENT_HOST}")
    path = f"{servers.root}/{server_hex_num}/{image.hash}{ext}"
    if dir_ in {"webp", "avif"}:
        return origin / path
    return origin / dir_ / path


def _re_int_or_none(pattern: str, string: str) -> int | None:
    if match := re.search(pattern, string):
        return int(match.group(1).removesuffix("/"))


def _decode_nozomi_resp(data: bytes) -> tuple[int, ...]:
    return struct.unpack(f">{(len(data) / 4):.0f}I", data)


def _parse_search_query(query_word: str) -> SearchArgs:
    query_word = query_word.replace("_", " ")
    left_side, _, right_side = query_word.partition(":")
    if left_side == "language":
        return SearchArgs(None, "index", right_side)
    if left_side in {"female", "male"}:
        return SearchArgs("tag", query_word)
    return SearchArgs(left_side, right_side)


def _build_nozomi_url(name: str, language: str, colletion_type: str) -> AbsoluteHttpURL:
    if name == "index":
        return _LTN_SERVER / f"{name}-{language}.nozomi"

    return _LTN_SERVER / colletion_type / f"{name}-{language}.nozomi"


def _decode_servers(js_text: str) -> Servers:
    root = _re_int_or_none(r"b: '(.+)'", js_text)
    num = _re_int_or_none(r"o = (\d+); break;", js_text)
    default_num = _re_int_or_none(r"var o = (\d+)", js_text)

    assert root is not None
    assert num is not None
    servers = Servers(root, default_num)

    for case in (match.group(1) for match in re.finditer(r"case (\d+):", js_text)):
        servers[int(case)] = num
    return servers
