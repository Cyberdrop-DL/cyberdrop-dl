from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


PRIMARY_URL = AbsoluteHttpURL("https://masahub.com")


class MasahubCrawler(Crawler):
    SUPPORTED_DOMAINS = "masa49.com", "masahub.com", "masahub2.com", "masafun.net", "lol49.com", "vido99.com"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Videos": "/title", "Search": "?s="}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "masahub.com"
    FOLDER_DOMAIN: ClassVar[str] = "Masahub"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if query:= scrape_item.url.query.get("s"):
            return await self.search(scrape_item, query)
        elif len(scrape_item.url.parts) >= 2:
            return await self.video(scrape_item)
        raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return
        soup = await self.request_soup(scrape_item.url)
        download_url = self.parse_url(soup.select_one("a.video-btn, a.download-btn").get("href"))
        title = soup.select_one("div.posts > h1 > strong, div.video_page_toolbar > h1").text.strip()
        filename, ext = self.get_filename_and_ext(download_url.name)
        custom_filename = self.create_custom_filename(title, ext)
        return await self.handle_file(download_url, scrape_item, filename, ext, custom_filename=custom_filename)

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        title = self.create_title(query)
        scrape_item.setup_as_album(title)
        async for soup in self.web_pager(scrape_item.url, next_page_selector="div > a:contains('Next')"):
            for _, new_scrape_item in self.iter_children(scrape_item, soup,"a.title, div.title > a")
                self.create_task(self.run(new_scrape_item))
