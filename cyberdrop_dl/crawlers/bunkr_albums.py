from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class BunkrAlbumsCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Search": "/?search=<query>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://balbums.st")
    DOMAIN: ClassVar[str] = "bunkr-albums"
    FOLDER_DOMAIN: ClassVar[str] = "Bunkr-Albums"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("bunkr-albums.io",)
    NEXT_PAGE_SELECTOR: ClassVar[str] = "a.btn-ghost:-soup-contains(Next)[href*='search=']"
    ALLOW_EMPTY_PATH: ClassVar[bool] = True

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [] | [""] if query := scrape_item.url.query.get("search"):
                return await self.search(scrape_item, query)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        title = self.create_title(query)
        scrape_item.setup_as_profile(title)
        async for soup in self.web_pager(scrape_item.url.update_query(per=100)):
            for _, new_scrape_item in self.iter_children(scrape_item, soup, "main section.grid a"):
                self.handle_external_links(new_scrape_item)
