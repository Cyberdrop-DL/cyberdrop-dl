from __future__ import annotations

import dataclasses
import json
import random
import time
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl import env
from cyberdrop_dl.crawlers.crawler import Crawler, DBPathBuilder, SupportedPaths, auto_task_id
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import css, dates
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem

SUPPORTED_FORMATS = "mp3-320", "mp3", "aac-hi", "wav", "flac", "vorbis", "aiff", "alas"  # Ordered by compatibility
USE_FORMATS = tuple(dict.fromkeys((env.BANDCAMP_FORMATS).split(","))) if env.BANDCAMP_FORMATS else SUPPORTED_FORMATS


@dataclasses.dataclass(slots=True, frozen=True)
class Format:
    ext: str
    codec: str
    url: AbsoluteHttpURL
    name: str


class BandcampCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/album/<slug>",
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
            case ["album", _, *_]:
                return await self.album(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem) -> None:
        album = await self._get_page_info(scrape_item.url)
        album_title: str = album["current"]["title"]
        scrape_item.setup_as_album(self.create_title(album_title))
        origin = scrape_item.url.origin()

        for track in album["trackinfo"]:
            if track.get("duration"):
                web_url = self.parse_url(track["title_link"], origin)
                new_scrape_item = scrape_item.create_child(web_url)
                self.create_task(self._song_task(new_scrape_item, track))
                scrape_item.add_children()

    @error_handling_wrapper
    async def song(self, scrape_item: ScrapeItem, fallback_track_info: dict[str, Any] | None = None) -> None:
        album = await self._get_page_info(scrape_item.url)
        track: dict[str, Any] = (album["trackinfo"][0] if album.get("trackinfo") else fallback_track_info) or {}
        current: dict[str, Any] = album["current"]

        track["free_download"] = album.get("freeDownloadPage")
        track["publish_date"] = current["publish_date"]
        track["artist"] = artist = current.get("artist") or album["artist"]
        track["title"] = (current.get("title") or track["title"]).removeprefix(f"{artist} - ")
        assert artist
        await self._track(scrape_item, track)

    _song_task = auto_task_id(song)

    async def _track(self, scrape_item: ScrapeItem, track: dict[str, Any]) -> None:
        scrape_item.possible_datetime = dates.parse_http(track["publish_date"])
        best_format = await self._get_best_format(track.pop("free_download"), track["file"])
        full_name = f"{track['artist']} - {track['title']}{best_format.ext}"
        filename, ext = self.get_filename_and_ext(full_name)
        db_url = scrape_item.url.with_query(None).with_fragment(best_format.name)
        await self.handle_file(
            db_url,
            scrape_item,
            full_name,
            ext,
            debrid_link=best_format.url,
            custom_filename=filename,
            metadata=track,
        )

    async def _get_page_info(self, url: AbsoluteHttpURL, name: str = "tralbum") -> dict[str, Any]:
        soup = await self.request_soup(url)
        attr_name = f"data-{name}"
        return json.loads(css.select(soup, f"[{attr_name}]", attr_name))

    async def _get_best_format(self, free_download: str | None, file_info: dict[str, str] | None) -> Format:
        if free_download:
            free_download_url = self.parse_url(free_download)
            if free_download_url.query.get("type") == "track":
                return await self._get_free_download(free_download_url)

        if not file_info:
            raise ScrapeError(402, "No streaming or download formats available (purchase only)")

        return max(self._parse_formats(file_info), key=lambda x: _score(x.codec))

    def _parse_formats(self, file_info: dict[str, str]) -> Generator[Format]:
        for name, format_url in file_info.items():
            codec = name.partition("-")[0]
            yield Format(
                url=self.parse_url(format_url),
                ext=f".{codec}",
                codec=codec,
                name=name,
            )

    async def _get_free_download(self, free_download_url: AbsoluteHttpURL) -> Format:
        blob = await self._get_page_info(free_download_url, "blob")
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
