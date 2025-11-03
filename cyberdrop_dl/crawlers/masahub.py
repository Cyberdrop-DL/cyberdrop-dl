from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


PRIMARY_URL = AbsoluteHttpURL("https://masahub.com")


class MasahubCrawler(Crawler):
    SUPPORTED_DOMAINS = "masa49.com", "masahub.com", "masahub2.com", "masafun.net", "lol49.com"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Videos": "/title", "Search": "?s="}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "masahub.com"
    FOLDER_DOMAIN: ClassVar[str] = "Masahub"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if scrape_item.url.query.get("s"):
            await self.search(scrape_item)
        else:
            await self.video(scrape_item)

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return
        soup = await self.request_soup(scrape_item.url)
        download_url = AbsoluteHttpURL(soup.select_one("a.video-btn, a.download-btn")["href"])
        title = soup.select_one("div.posts > h1 > strong, div.video_page_toolbar > h1").text.strip()
        filename, ext = self.get_filename_and_ext(download_url.name)

        await self.handle_file(
            scrape_item.url, scrape_item, filename, ext, debrid_link=download_url, custom_filename=f"{title}{ext}"
        )

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem) -> None:
        async for soup in self.web_pager(scrape_item.url, next_page_selector="div > a:contains('Next')"):
            videos = soup.select("a.title, div.title > a")
            for video in videos:
                video_url = AbsoluteHttpURL(video["href"])
                new_scrape_item = scrape_item.create_new(url=video_url)
                await self.video(new_scrape_item)
