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
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Video": "/videos/<video_id>/...", "Search": "/search?s=<query>",}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "desivideo.net"
    FOLDER_DOMAIN: ClassVar[str] = "DesiVideo"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["search"] if query:= scrape_item.url.query.get("s"):
               return await self.search(scrape_item, query)
            case ["videos", video_id, *_]
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return
        soup = await self.request_soup(scrape_item.url)
        video_url = self.parse_url(soup.select_one("video.fluid-player > source").get("src"))
        title = soup.select_one("strong.bread-current").text.strip()
        filename, ext = self.get_filename_and_ext(video_url.name)

        custom_filename = self.create_custom_filename(title, ext, file_id=video_id)
        return await self.handle_file(video_url, scrape_item, filename, ext, custom_filename=f"{title}{ext}")

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        title = self.create_title(query)
        scrape_item.setup_as_album(title)
        async for soup in self.web_pager(scrape_item.url, next_page_selector="li.page-item > a:contains('›')"): 
            for _, new_scrape_item in self.iter_children(scrape_item, soup,"div.videos-list > article > a"):
                self.create_task(self.run(new_scrape_item))
