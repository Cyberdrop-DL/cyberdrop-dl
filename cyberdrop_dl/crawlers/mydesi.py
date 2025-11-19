from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.data_structures import Resolution
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class MyDesiCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "fry99.com", "lolpol.com", "mydesi.net"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Videos": "/title",
        "Search": "/search/<query>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://lolpol.com")
    DOMAIN: ClassVar[str] = "mydesi.net"
    FOLDER_DOMAIN: ClassVar[str] = "MyDesi"
    NEXT_PAGE_SELECTOR: ClassVar[str] = "a.page-link:-soup-contains(»)"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["search", query, *_]:
                return await self.search(scrape_item, query)
            case [_]:
                return await self.video(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        resolution, download_url = self.select_highest_quality_video(soup)
        filename, ext = self.get_filename_and_ext(download_url.name)
        metadata: dict[str, str] = css.get_json_ld(soup)["subjectOf"]
        upload_date = metadata.get("uploadDate", "")
        title = metadata["name"]
        scrape_item.possible_datetime = self.parse_iso_date(upload_date)
        custom_filename = self.create_custom_filename(title, ext, resolution=resolution)
        return await self.handle_file(download_url, scrape_item, filename, ext, custom_filename=custom_filename)

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        title = self.create_title(f"{query} [search]")
        scrape_item.setup_as_album(title)

        async for soup in self.web_pager(scrape_item.url):
            for _, new_scrape_item in self.iter_children(scrape_item, soup, "a.infos"):
                self.create_task(self.run(new_scrape_item))

    def select_highest_quality_video(self, soup: BeautifulSoup) -> tuple[Resolution, AbsoluteHttpURL]:
        def parse():
            for src in soup.select("#video-rate > a"):
                quality = css.get_attr(src, "title")
                link = css.get_attr(src, "href")
                resolution = Resolution.highest() if "original" in quality.casefold() else Resolution.parse(quality)
                yield resolution, self.parse_url(link)

        return max(parse())
