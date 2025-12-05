from __future__ import annotations

import itertools
import json
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.logger import log_debug
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem

class Selectors:
    APP_JSON = "script#__NUXT_DATA__"
    USER_NAME = "div.user-profile-card h1"
    VIDEOS = "div.videos-grid-fixed a"

API_ENTRYPOINT = AbsoluteHttpURL("https://pmvhaven.com/api/")
PRIMARY_URL = AbsoluteHttpURL("https://pmvhaven.com")
CATEGORIES = "Hmv", "Pmv", "Hypno", "Tiktok", "KoreanBJ"


class PMVHavenCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Category": "/category/...",
        "Music": "/music/...",
        "Playlist": "/playlist/...",
        "Search results": "/search/...",
        "Star": "/star/...",
        "Tag": "/tags/...",
        "Users": "/profile/...",
        "Video": "/video/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "pmvhaven"
    FOLDER_DOMAIN: ClassVar[str] = "PMVHaven"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if "video" in scrape_item.url.parts:
            return await self.video(scrape_item)
        if "star" in scrape_item.url.parts:
            return await self.model(scrape_item)
        if "tags" in scrape_item.url.parts:
            return await self.tag(scrape_item)
        if "music" in scrape_item.url.parts:
            return await self.music(scrape_item)
        if "search" in scrape_item.url.parts:
            return await self.search(scrape_item)
        if "category" in scrape_item.url.parts:
            return await self.category(scrape_item)
        if "profile" in scrape_item.url.parts:
            return await self.profile(scrape_item)
        if "playlist" in scrape_item.url.parts:
            return await self.playlist(scrape_item)
        raise ValueError

    @error_handling_wrapper
    async def profile(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)
        username = css.select_text(soup, Selectors.USER_NAME)
        title = f"{username} [user]"
        title = self.create_title(title)
        scrape_item.setup_as_profile(title)

        await self.process_video_list(scrape_item, soup)


    @error_handling_wrapper
    async def playlist(self, scrape_item: ScrapeItem, add_suffix: bool = True) -> None:
        ...

    @error_handling_wrapper
    async def model(self, scrape_item: ScrapeItem) -> None:
        ...

    @error_handling_wrapper
    async def creator(self, scrape_item: ScrapeItem) -> None:
        ...

    @error_handling_wrapper
    async def music(self, scrape_item: ScrapeItem) -> None:
        ...

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)
        tags = scrape_item.url.query.get("tags")
        title = f"{tags} [search]"
        title = self.create_title(title)
        scrape_item.setup_as_album(title)

        await self.process_video_list(scrape_item, soup)

    @error_handling_wrapper
    async def category(self, scrape_item: ScrapeItem) -> None:
        ...

    @error_handling_wrapper
    async def tag(self, scrape_item: ScrapeItem) -> None:
        ...

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        info_table = json.loads(css.select_text(soup, Selectors.APP_JSON))
        video_info_idx = next((data["video"] for data in info_table if isinstance(data, dict) and "uploaderVideosCount" in data), None)

        await self.process_video_info(scrape_item, info_table, info_table[video_info_idx])

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    @error_handling_wrapper
    async def process_video_list(self, scrape_item: ScrapeItem, soup: BeautifulSoup) -> None:
        info_table = json.loads(css.select_text(soup, Selectors.APP_JSON))
        video_info_list = [data for data in info_table if isinstance(data, dict) and "videoUrl" in data]
        for video_info in video_info_list:
            await self.process_video_info(scrape_item, info_table, video_info)

    @error_handling_wrapper
    async def process_video_info(self, scrape_item: ScrapeItem, info_table: dict, video_info: dict) -> None:
        log_debug(json.dumps(video_info, indent=4))
        link_str: str = info_table[video_info["videoUrl"]]
        if not link_str:
            raise ScrapeError(422, message="No video source found")

        video_id: str = info_table[video_info["_id"]]
        resolution: str | None = None
        if height := video_info.get("height"):
            resolution = info_table[height]
        title_idx: int = video_info.get("title") or video_info["uploadTitle"]
        title: str = info_table[title_idx]
        link_str: str = info_table[video_info["videoUrl"]]
        scrape_item.possible_datetime = self.parse_date(info_table[video_info["uploadDate"]])

        link = self.parse_url(link_str)
        filename, ext = self.get_filename_and_ext(link.name, assume_ext=".mp4")
        custom_filename = self.create_custom_filename(title, ext, file_id=video_id, resolution=resolution)
        await self.handle_file(link, scrape_item, filename, ext, custom_filename=custom_filename)

