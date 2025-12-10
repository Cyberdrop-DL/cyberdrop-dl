from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from typing import Any

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class Selectors:
    APP_JSON = "script#__NUXT_DATA__"
    USER_NAME = "div.user-profile-card h1"


PRIMARY_URL = AbsoluteHttpURL("https://pmvhaven.com")


class PMVHavenCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Playlist": "/playlists/...",
        "Search results": "/search/...",
        "Users": "/profile/...",
        "Video": "/video/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "pmvhaven"
    FOLDER_DOMAIN: ClassVar[str] = "PMVHaven"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if "video" in scrape_item.url.parts:
            return await self.video(scrape_item)
        if "search" in scrape_item.url.parts:
            return await self.search(scrape_item)
        if "profile" in scrape_item.url.parts:
            return await self.profile(scrape_item)
        if "playlists" in scrape_item.url.parts:
            return await self.playlist(scrape_item)
        raise ValueError

    @error_handling_wrapper
    async def profile(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)
        username = css.select_text(soup, Selectors.USER_NAME)
        title = f"{username} [user]"
        title = self.create_title(title)
        scrape_item.setup_as_profile(title)

        nuxt_data = css.get_nuxt_data(soup)
        await self.process_video_list(scrape_item, nuxt_data)

    @error_handling_wrapper
    async def playlist(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)
        nuxt_data = css.get_nuxt_data(soup)
        playlist = css.parse_nuxt_obj(nuxt_data, "playlist")
        playlist_name = playlist["name"]

        title = f"{playlist_name} [playlist]"
        title = self.create_title(title)
        scrape_item.setup_as_album(title)

        await self.process_video_list(scrape_item, nuxt_data)

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)
        tags = scrape_item.url.query.get("tags") or scrape_item.url.query.get("musicSong")
        title = f"{tags} [search]"
        title = self.create_title(title)
        scrape_item.setup_as_album(title)

        nuxt_data = css.get_nuxt_data(soup)
        await self.process_video_list(scrape_item, nuxt_data)

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        nuxt_data = css.get_nuxt_data(soup)
        video = css.parse_nuxt_obj(nuxt_data, "video", "uploaderVideosCount")
        await self.process_video_info(scrape_item, video)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    @error_handling_wrapper
    async def process_video_list(self, scrape_item: ScrapeItem, nuxt_data: list[Any]) -> None:
        for video_info in css.parse_nuxt_objs(nuxt_data, "videoUrl"):
            await self.process_video_info(scrape_item, video_info)

    @error_handling_wrapper
    async def process_video_info(self, scrape_item: ScrapeItem, video_info: dict[str, Any]) -> None:
        link_str: str = video_info["videoUrl"]
        video_id: str = video_info["_id"]
        resolution = video_info["height"]
        title = video_info.get("title") or video_info["uploadTitle"]
        link_str: str = video_info["videoUrl"]
        scrape_item.possible_datetime = self.parse_date(video_info["uploadDate"])

        link = self.parse_url(link_str)
        filename, ext = self.get_filename_and_ext(link.name, assume_ext=".mp4")
        custom_filename = self.create_custom_filename(title, ext, file_id=video_id, resolution=resolution)
        await self.handle_file(link, scrape_item, filename, ext, custom_filename=custom_filename)
