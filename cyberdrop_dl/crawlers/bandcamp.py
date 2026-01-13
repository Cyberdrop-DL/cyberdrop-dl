from __future__ import annotations

import dataclasses
import json
import random
import time
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl import env
from cyberdrop_dl.crawlers.crawler import Crawler, DBPathBuilder, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, dates
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem

SUPPORTED_FORMATS = "mp3-320", "aac-hi", "mp3", "flac", "vorbis", "wav", "alas", "aiff"  # Ordered by preference
USE_FORMATS = tuple(dict.fromkeys((env.BANDCAMP_FORMATS).split(","))) if env.BANDCAMP_FORMATS else SUPPORTED_FORMATS


@dataclasses.dataclass(slots=True, frozen=True)
class Format:
    ext: str
    codec: str
    url: AbsoluteHttpURL
    name: str


class BandcampCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Song": "/track/<slug>",
        "**NOTE**": (
            f"You can set 'CDL_BANDCAMP_FORMATS' env var to a comma separated list of formats to download (Ordered by preference)"
            f" [Default = {','.join(SUPPORTED_FORMATS)!r}]"
        ),
    }
    DOMAIN: ClassVar[str] = "bandcamp"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://bandcamp.com")
    create_db_path = staticmethod(DBPathBuilder.path_qs_frag)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["track", _, *_]:
                return await self.song(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def song(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)
        tralbum = _get_attr_data(soup, "tralbum")

        track: dict[str, Any] = tralbum["trackinfo"][0]
        current: dict[str, Any] = tralbum["current"]
        artist: str = current.get("artist") or tralbum["artist"]
        track_name: str = (current.get("title") or track["title"]).removeprefix(f"{artist} - ")
        assert artist

        scrape_item.possible_datetime = dates.parse_http(current.get("publish_date") or tralbum["album_publish_date"])
        best_format = await self._get_best_format(tralbum["freeDownloadPage"], track["file"])
        full_name = f"{artist} - {track_name}{best_format.ext}"
        filename, ext = self.get_filename_and_ext(full_name)
        db_url = scrape_item.url.with_query(None).with_fragment(best_format.name)

        await self.handle_file(
            db_url,
            scrape_item,
            full_name,
            ext,
            debrid_link=best_format.url,
            custom_filename=filename,
        )

    async def _get_best_format(self, free_download: str | None, file_info: dict[str, str]) -> Format:
        if free_download:
            free_download_url = self.parse_url(free_download)
            return await self._get_free_download(free_download_url)

        return max(self._parse_formats(file_info), key=lambda x: _score(x.codec))

    def _parse_formats(self, file_info: dict[str, str]) -> Generator[Format]:
        for name, format_url in file_info.items():
            codec, _ = name.split("-", 1)
            yield Format(
                url=self.parse_url(format_url),
                ext=f".{codec}",
                codec=codec,
                name=name,
            )

    async def _get_free_download(self, free_download_url: AbsoluteHttpURL) -> Format:
        soup = await self.request_soup(free_download_url)
        blob = _get_attr_data(soup, "blob")
        downloads: dict[str, dict[str, str]] = blob["download_items"][0]["downloads"]

        name = max(downloads, key=lambda x: _score(x))
        download_url = downloads[name]["url"]
        ext_map: dict[str, str] = {fmt["name"]: fmt["file_extension"] for fmt in blob["download_formats"]}

        stat_result = await self._stat_free_download(download_url)
        return Format(
            url=self.parse_url(stat_result["retry_url"]),
            ext=ext_map[name],
            codec=name.partition("-")[0],
            name=name,
        )

    async def _stat_free_download(self, download_url: str) -> dict[str, str]:
        rand = int(time.time() * 1000 * random.random())
        stat_url = self.parse_url(download_url.replace("/download/", "/statdownload/")).update_query({".rand": rand})
        stat = await self.request_text(stat_url)
        return json.loads(stat[stat.find("{") : stat.rfind("}") + 1])


def _score(name: str) -> int:
    def scores():
        for idx, fmt in enumerate(reversed(USE_FORMATS)):
            if fmt in name.casefold():
                yield idx
        yield -1

    return max(scores())


def _get_attr_data(soup: BeautifulSoup, name: str) -> dict[str, Any]:
    attr_name = f"data-{name}"
    return json.loads(css.select(soup, f"[{attr_name}]", attr_name))
