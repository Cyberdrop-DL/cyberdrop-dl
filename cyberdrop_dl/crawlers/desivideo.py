from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


PRIMARY_URL = AbsoluteHttpURL("https://desivideo.net")


class DesiVideoCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Videos": "/videos/", "Search": "/search?s="}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "desivideo.net"
    FOLDER_DOMAIN: ClassVar[str] = "DesiVideo"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if scrape_item.url.parts[1] == "search" and scrape_item.url.query.get("s"):
            return await self.search(scrape_item)
        elif scrape_item.url.parts[1] == "videos":
            return await self.video(scrape_item)
        raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return
        soup = await self.request_soup(scrape_item.url)
        video_url = self.parse_url(soup.select_one("video.fluid-player > source").get("src"))
        title = soup.select_one("strong.bread-current").text.strip()
        filename, ext = self.get_filename_and_ext(video_url.name)

        return await self.handle_file(video_url, scrape_item, filename, ext, custom_filename=f"{title}{ext}")

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem) -> None:
        title = self.create_title(scrape_item.url.query.get("s"))
        scrape_item.setup_as_album(title)
        async for soup in self.web_pager(scrape_item.url, next_page_selector="li.page-item > a:contains('›')"):  # noqa: RUF001
            videos: tuple[BeautifulSoup] = soup.select("div.videos-list > article > a")
            for video in videos:
                video_url = self.parse_url(video.get("href"))
                new_scrape_item = scrape_item.create_child(video_url)
                self.create_task(self.run(new_scrape_item))
