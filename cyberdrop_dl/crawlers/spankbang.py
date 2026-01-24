from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, NamedTuple

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import css, json
from cyberdrop_dl.utils.utilities import error_handling_wrapper, get_text_between

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


PRIMARY_URL = AbsoluteHttpURL("https://spankbang.com/")
DEFAULT_QUALITY = "main"
RESOLUTIONS = ["4k", "2160p", "1440p", "1080p", "720p", "480p", "360p", "240p"]  # best to worst


class Selector:
    VIDEO_REMOVED = "#video_removed, #video_removed"
    VIDEOS = ".video-list > .video-item > a"
    STREAM_DATA = ".main-container > script:-soup-contains('var stream_data')"
    PLAYLIST_TITLE = "[data-testid=playlist-title]"


class Format(NamedTuple):
    resolution: str
    link_str: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Video:
    id: str
    title: str
    best_format: Format


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
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "spankbang"
    FOLDER_DOMAIN: ClassVar[str] = "SpankBang"

    async def async_startup(self) -> None:
        self.update_cookies({"country": "US", "age_pass": 1})

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [id_, "playlist", _]:
                playlist_id, _, video_id = id_.partition("-")
                if video_id:
                    return await self.video(scrape_item, video_id)
                return await self.playlist(scrape_item, playlist_id)
            case [video_id, "video" | "embed" | "play", *_]:
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def playlist(self, scrape_item: ScrapeItem, playlist_id: str) -> None:
        page_url = scrape_item.url
        title: str = ""

        for page in itertools.count(1):
            soup = await self.request_soup(page_url, impersonate=True)

            if not title:
                name = css.select_text(soup, Selector.PLAYLIST_TITLE)
                scrape_item.url = scrape_item.url.origin() / playlist_id / "playlist" / name
                title = self.create_title(name, playlist_id)
                scrape_item.setup_as_album(title, album_id=playlist_id)

            n_videos = 0

            for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.VIDEOS):
                n_videos += 1
                self.create_task(self.run(new_scrape_item))

            if n_videos < 100:
                break

            page_url = scrape_item.url / f"{page + 1}"

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        canonical_url = scrape_item.url.origin() / video_id / "video"
        scrape_item.url = canonical_url.with_host(self.PRIMARY_URL.host)
        if await self.check_complete_from_referer(canonical_url):
            return

        soup = await self.request_soup(canonical_url, impersonate=True)
        if soup.select_one(Selector.VIDEO_REMOVED) or "This video is no longer available" in soup.get_text():
            raise ScrapeError(410)

        video = _parse_video(soup)
        resolution, link_str = video.best_format
        link = self.parse_url(link_str)
        filename, ext = self.get_filename_and_ext(link.name)
        custom_filename = self.create_custom_filename(video.title, ext, file_id=video.id, resolution=resolution)
        await self.handle_file(link, scrape_item, filename, ext, custom_filename=custom_filename)


def _parse_video(soup: BeautifulSoup) -> Video:
    title_tag = css.select(soup, "div#video h1")
    stream_js_text = css.select_text(soup, Selector.STREAM_DATA)
    video_id = get_text_between(stream_js_text, "ana_video_id = ", ";").strip("'")
    stream_data = json.load_js_obj(get_text_between(stream_js_text, "stream_data = ", ";"))
    return Video(
        id=video_id,
        title=css.get_attr_or_none(title_tag, "title") or css.get_text(title_tag),
        best_format=_get_best_quality(stream_data),
    )


def _get_best_quality(stream_data: dict[str, list[str]]) -> Format:
    """Returns name and URL of the best available quality."""
    for res in RESOLUTIONS:
        if value := stream_data.get(res):
            return Format(res, value[-1])
    raise ScrapeError(422, message="Unable to get download link")
