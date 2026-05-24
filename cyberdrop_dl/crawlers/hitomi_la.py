from __future__ import annotations

import asyncio
import dataclasses
import json
import re
import struct
from collections import defaultdict
from datetime import timedelta
from typing import TYPE_CHECKING, ClassVar, Required, TypedDict

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import error_handling_wrapper
from cyberdrop_dl.utils.filepath import get_filename_and_ext

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.url_objects import ScrapeItem


ALLOW_AVIF = False
GALLERY_PARTS = "cg", "doujinshi", "galleries", "gamecg", "imageset", "manga", "reader", "anime"
COLLECTION_PARTS = "artist", "character", "group", "series", "tag", "type"
CONTENT_HOST = "gold-usergeneratedcontent.net"
LTN_SERVER = AbsoluteHttpURL(f"https://ltn.{CONTENT_HOST}/")
PRIMARY_URL = AbsoluteHttpURL("https://hitomi.la")
VIDEOS_SERVER = AbsoluteHttpURL(f"https://streaming.{CONTENT_HOST}/")


@dataclasses.dataclass(slots=True)
class SearchArgs:
    area: str | None
    tag: str
    language: str = "all"

    @property
    def url(self) -> AbsoluteHttpURL:
        name = f"{self.tag}-{self.language}.nozomi"
        if self.area:
            return LTN_SERVER / "n" / self.area / name
        return LTN_SERVER / "n" / name


class Servers(defaultdict[int, int]):
    _EXPIRES_AFTER: ClassVar[timedelta] = timedelta(minutes=40)

    def __init__(self, root: int, default: int | None = None) -> None:
        if default is None:
            default = 0
        super().__init__(lambda: default)
        self.root: int = root


class Image(TypedDict, total=False):
    hash: Required[str]
    name: Required[str]
    hasavif: int


class Gallery(TypedDict, total=False):
    blocked: Required[int]
    id: Required[str]
    title: Required[str]
    files: Required[list[Image]]
    type: Required[str]
    date: Required[str]
    datepublished: str
    videofilename: str


class HitomiLaCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Gallery": tuple(f"/{g}/<slug>" for g in GALLERY_PARTS),
        "Collection": tuple(f"/{g}/<slug>" for g in COLLECTION_PARTS),
        "Search": "/search.html?<query>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "hitomi.la"
    _RATE_LIMIT: ClassVar[tuple[float, float]] = 3, 1

    def __post_init__(self) -> None:
        self._semaphore = asyncio.Semaphore(3)
        self._servers = aio.cached(self._servers)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [part, _]:
                if part in GALLERY_PARTS:
                    return await self.gallery(scrape_item)
                if part in COLLECTION_PARTS:
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
            title = self.create_title(f"{name} [{language}]")
            nozomi_url = LTN_SERVER / f"{name}-{language}.nozomi"
        else:
            title = self.create_title(f"{name} [{colletion_type}][{language}]")
            nozomi_url = LTN_SERVER / colletion_type / f"{name}-{language}.nozomi"

        scrape_item.setup_as_profile(title)
        nozomi = await self._request_nozomi(nozomi_url)

        for idx, gallery_id in enumerate(nozomi, 1):
            new_item = scrape_item.create_child(self.PRIMARY_URL / f"galleries/{gallery_id}.html")
            self.create_task(self.run(new_item))
            scrape_item.add_children()
            if idx % 300:
                await asyncio.sleep(0)

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, search_query: str) -> None:
        scrape_item.setup_as_profile(self.create_title(f"{search_query} [search]"))
        gallery_sets = [gallery_set async for gallery_set in self._request_galleries(search_query)]
        if not gallery_sets:
            raise ScrapeError(204)

        for gallery_id in sorted(set.intersection(*gallery_sets), reverse=True):
            new_scrape_item = scrape_item.create_child(PRIMARY_URL / f"galleries/{gallery_id}.html")
            await self.run(new_scrape_item)
            scrape_item.add_children()

    async def _request_nozomi(self, url: AbsoluteHttpURL) -> tuple[int, ...]:
        async with self.request(url, headers={"Referer": str(PRIMARY_URL), "Origin": str(PRIMARY_URL)}) as response:
            content = await response.read()

        return _decode_nozomi_resp(content)

    async def _request_galleries(self, search_query: str) -> AsyncGenerator[set[int]]:
        # https://ltn.gold-usergeneratedcontent.net/search.js
        # This is partial implementation. Only parses tagged words, ex `female:dark_skin`
        # Free form query searches are ignored
        words = (parse_query_word(word) for word in search_query.split(" ") if ":" in word)
        for nozomi_search_args in words:
            nozomi = await self._request_nozomi(nozomi_search_args.url)
            yield set(nozomi)

    @error_handling_wrapper
    async def gallery(self, scrape_item: ScrapeItem) -> None:
        gallery_id = scrape_item.url.name.split("-")[-1].removesuffix(".html")
        gallery = await self._request_gallery(gallery_id)
        if gallery["blocked"]:
            raise ScrapeError(403)

        scrape_item.url = PRIMARY_URL / "galleries" / gallery_id
        title = self.create_title(f"{gallery['title']} [{gallery['type']}]", gallery["id"])
        scrape_item.setup_as_album(title, album_id=gallery["id"])
        date_str = gallery.get("datepublished") or gallery["date"]
        scrape_item.uploaded_at = self.parse_iso_date(date_str)
        await self.process_gallery(scrape_item, gallery)

    async def _request_gallery(self, gallery_id: str) -> Gallery:
        gallery_url = LTN_SERVER / f"galleries/{gallery_id}.js"
        js_text = await self.request_text(gallery_url, headers=self.headers)
        return json.loads(js_text.split("=", 1)[-1])

    async def _servers(self) -> Servers:
        # https://ltn.gold-usergeneratedcontent.net/gg.js
        gg_url = LTN_SERVER / "gg.js"
        js_text = await self.request_text(gg_url)
        return _decode_servers(js_text)

    async def process_gallery(self, scrape_item: ScrapeItem, gallery: Gallery) -> None:
        servers = await self._servers()
        gallery_reader_url = PRIMARY_URL / f"reader/{gallery['id']}.html"
        results = await self.get_album_results(gallery["id"])

        if video_filename := gallery.get("videofilename"):
            link = VIDEOS_SERVER / "videos" / video_filename
            filename, ext = self.get_filename_and_ext(video_filename)
            await self.handle_file(link, scrape_item, filename, ext)

        for index, image in enumerate(gallery["files"], 1):
            img_reader_url = gallery_reader_url.with_fragment(str(index))
            if self.check_album_results(img_reader_url, results):
                continue
            link = get_image_url(servers, image)
            new_scrape_item = scrape_item.create_child(img_reader_url)
            filename, ext = self.get_filename_and_ext(image["name"])
            custom_filename = self.create_custom_filename(filename, link.suffix)
            await self.handle_file(
                img_reader_url, new_scrape_item, filename, ext, custom_filename=custom_filename, debrid_link=link
            )


def get_image_url(servers: Servers, image: Image) -> AbsoluteHttpURL:
    ext = "avif" if ALLOW_AVIF and image.get("hasavif") else "webp"
    return url_from_hash(servers, image, ext, ext=f".{ext}")


def url_from_hash(servers: Servers, image: Image, dir_: str, ext: str | None = None) -> AbsoluteHttpURL:
    # https://ltn.gold-usergeneratedcontent.net/common.js
    if ext is None:
        _, ext = get_filename_and_ext(image["name"])

    image_hash = image["hash"]
    server_hex_num = int(image_hash[-1] + image_hash[-3:-1], base=16)
    server_num = servers[server_hex_num] + 1
    origin = AbsoluteHttpURL(f"https://{ext[1]}{server_num}.{CONTENT_HOST}")
    path = f"{servers.root}/{server_hex_num}/{image_hash}{ext}"
    if dir_ in {"webp", "avif"}:
        return origin / path
    return origin / dir_ / path


def _re_int_or_none(pattern: str, string: str) -> int | None:
    if match := re.search(pattern, string):
        return int(match.group(1).removesuffix("/"))


def _decode_nozomi_resp(data: bytes) -> tuple[int, ...]:
    return struct.unpack(f">{(len(data) / 4):.0f}I", data)


def parse_query_word(query_word: str) -> SearchArgs:
    query_word = query_word.replace("_", " ")
    left_side, _, right_side = query_word.partition(":")
    if left_side == "language":
        return SearchArgs(None, "index", right_side)
    if left_side in {"female", "male"}:
        return SearchArgs("tag", query_word)
    return SearchArgs(left_side, right_side)


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
