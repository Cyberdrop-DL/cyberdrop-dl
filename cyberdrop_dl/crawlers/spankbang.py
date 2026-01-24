from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.mediaprops import Resolution
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import css, json
from cyberdrop_dl.utils.utilities import error_handling_wrapper, get_text_between

if TYPE_CHECKING:
    from collections.abc import Generator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class Selector:
    VIDEO_REMOVED = "#video_removed, #video_removed"
    VIDEOS = ".video-list > .video-item > a"
    STREAM_DATA = ".main-container > script:-soup-contains('var stream_data')"
    PLAYLIST_TITLE = "[data-testid=playlist-title]"
    NEXT_PAGE = ".pagination li.next > a[href]"


@dataclasses.dataclass(frozen=True, slots=True)
class Video:
    id: str
    title: str
    resolution: Resolution
    best_mp4: str


class SpankBangCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Playlist": "/<playlist_id>/playlist/...",
        "Video": (
            "/<video_id>/video",
            "/<video_id>/embed",
            "/play/<video_id>",
            "<playlist_id>-<video_id>/playlist/...",
        ),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://spankbang.com")
    OLD_DOMAIND: ClassVar[tuple[str, ...]] = ("m.spankbang.com",)
    DOMAIN: ClassVar[str] = "spankbang"
    FOLDER_DOMAIN: ClassVar[str] = "SpankBang"
    _IMPERSONATE = True
    NEXT_PAGE_SELECTOR = Selector.NEXT_PAGE

    async def async_startup(self) -> None:
        self.update_cookies({"country": "US", "age_pass": 1})

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [id_, "playlist", _]:
                playlist_id, _, video_id = id_.partition("-")
                if video_id:
                    return await self.video(scrape_item, video_id)
                return await self.playlist(scrape_item, playlist_id)
            case [playlist_id, "playlist", _, _page]:
                return await self.playlist(scrape_item, playlist_id)
            case [video_id, "video" | "embed" | "play", *_]:
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def playlist(self, scrape_item: ScrapeItem, playlist_id: str) -> None:
        origin = scrape_item.url.origin()
        title: str = ""

        async for soup in self.web_pager(scrape_item.url, cffi=True, relative_to=origin):
            if not title:
                name = css.select_text(soup, Selector.PLAYLIST_TITLE)
                scrape_item.url = origin / playlist_id / "playlist" / name
                title = self.create_title(name, playlist_id)
                scrape_item.setup_as_album(title, album_id=playlist_id)

            for _, new_item in self.iter_children(scrape_item, soup, Selector.VIDEOS):
                new_item.url = new_item.url.with_host(origin.host)
                self.create_task(self.run(new_item))

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        # old referer logic. video_id may be canonical (unique per video) or relative (different on each playlist)
        relative_url = self.PRIMARY_URL / video_id / "video"
        if await self.check_complete_from_referer(relative_url):
            return

        await self._video_with_redirect(scrape_item)

    async def _video_with_redirect(self, scrape_item: ScrapeItem) -> None:
        async with self.request(scrape_item.url, impersonate=True) as resp:
            assert "video" in resp.url.parts
            scrape_item.url = resp.url.with_host(self.PRIMARY_URL.host)
            if await self.check_complete_from_referer(scrape_item):
                return

            soup = await resp.soup()

        if soup.select_one(Selector.VIDEO_REMOVED) or "This video is no longer available" in soup.get_text():
            raise ScrapeError(410)

        video = _parse_video(soup)
        link = self.parse_url(video.best_mp4)
        filename, ext = self.get_filename_and_ext(link.name)
        custom_filename = self.create_custom_filename(video.title, ext, file_id=video.id, resolution=video.resolution)
        await self.handle_file(link, scrape_item, filename, ext, custom_filename=custom_filename)


def _parse_video(soup: BeautifulSoup) -> Video:
    title_tag = css.select(soup, "div#video h1")
    stream_js_text = css.select_text(soup, Selector.STREAM_DATA)
    video_id = get_text_between(stream_js_text, "ana_video_id = ", ";").strip("'")
    stream_data = get_text_between(stream_js_text, "stream_data = ", ";")
    res, url = max(_parse_formats(stream_data))
    return Video(
        id=video_id,
        title=css.get_attr_or_none(title_tag, "title") or css.get_text(title_tag),
        resolution=res,
        best_mp4=url,
    )


def _parse_formats(stream_data: str) -> Generator[tuple[Resolution, str]]:
    formats: dict[str, list[str]] = json.load_js_obj(stream_data)
    for name, options in formats.items():
        if not options or "m3u8" in name:
            continue

        try:
            resolution = Resolution.parse(name)
        except ValueError:
            continue

        yield resolution, options[-1]
