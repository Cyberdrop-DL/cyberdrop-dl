from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


PRIMARY_URL = AbsoluteHttpURL("https://lolpol.com")


class MyDesiCrawler(Crawler):
    SUPPORTED_DOMAINS = "fry99.com", "lolpol.com", "mydesi.net"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Videos": "/title", "Search": "/search/"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "mydesi.net"
    FOLDER_DOMAIN: ClassVar[str] = "MyDesi"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if scrape_item.url.parts[1] == "search":
            return await self.search(scrape_item)
        elif len(scrape_item.url.parts) >= 2 and len(scrape_item.url.parts) <= 3:
            return await self.video(scrape_item)
        raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return
        soup = await self.request_soup(scrape_item.url)
        download_url = await self.select_highest_quality_video(soup)
        title = soup.select_one("div.col-12.col-md-8.col-left > h1").text.strip()
        filename, ext = self.get_filename_and_ext(download_url.name)

        metadata_script = json.loads(soup.select_one("script[type='application/ld+json']").string)
        upload_date = metadata_script.get("subjectOf", {}).get("uploadDate")
        scrape_item.possible_datetime = self.parse_date(upload_date) if upload_date else None

        return await self.handle_file(download_url, scrape_item, filename, ext, custom_filename=f"{title}{ext}")

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem) -> None:
        album_initialized: bool = False
        async for soup in self.web_pager(scrape_item.url, next_page_selector=self.paginate):
            if not album_initialized:
                title = self.create_title(soup.select_one("title").text.split("“")[1].split("”")[0])
                scrape_item.setup_as_album(title)
                album_initialized = True

            videos: tuple[BeautifulSoup] = soup.select("a.infos")
            for video in videos:
                video_url = self.parse_url(video.get("href"))
                new_scrape_item = scrape_item.create_child(video_url)
                self.create_task(self.run(new_scrape_item))

    async def select_highest_quality_video(self, soup) -> AbsoluteHttpURL:
        video_links = soup.select("a.btn.btn-dark.btn-sm")
        quality_map = {i.get("title"): i.get("href") for i in video_links}
        if not quality_map:
            raise ValueError("No video links found")
        if "Original" in quality_map:
            selected_url = quality_map["Original"]
        elif x := next((href for href in quality_map.values() if "4K" in href), None):
            selected_url = x
        else:
            selected_url = quality_map[max(quality_map.keys(), key=lambda x: int(x.rstrip("p")))]
        return self.parse_url(selected_url)

    def paginate(self, soup: BeautifulSoup) -> str | None:
        # Extract search term from RSS feed link
        RSS_Feed = soup.select("link[rel='alternate']")[-1].get("href")
        searchTerm = RSS_Feed.split("search/")[1].split("/feed")[0]

        # Determine current page number
        currentPage = 1
        body = soup.select_one("body.paged")
        if body:
            _class = next((c for c in body.get("class", []) if c.startswith("search-paged-")), None)
            currentPage = int(_class.split("search-paged-")[1]) if _class else 1

        next_page_url = self.PRIMARY_URL / f"search/{searchTerm}/page/{currentPage + 1}/"
        return str(next_page_url)
