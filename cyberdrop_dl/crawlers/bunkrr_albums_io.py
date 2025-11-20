from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class BunkrAlbumsIOCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Search": "/s?search=<query>"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://bunkr-albums.io/")
    DOMAIN: ClassVar[str] = "bunkr-albums.io"
    FOLDER_DOMAIN: ClassVar[str] = "Bunkr-Albums.io"
    NEXT_PAGE_SELECTOR: ClassVar[str] = "nav a:-soup-contains(Next)"
    SKIP_PRE_CHECK: ClassVar[bool] = True

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if query := scrape_item.url.query.get("search"):
            return await self.search(scrape_item, query)
        raise ValueError

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        title = self.create_title(query)
        scrape_item.setup_as_profile(title)
        async for soup in self.web_pager(scrape_item.url):
            for _, new_scrape_item in self.iter_children(scrape_item, soup, "main div.auto-rows-max a"):
                self.handle_external_links(new_scrape_item)
