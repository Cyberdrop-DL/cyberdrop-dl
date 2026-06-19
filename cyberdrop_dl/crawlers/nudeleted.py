from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._kvs import KernelVideoSharingCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import css

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.crawlers.crawler import SupportedPaths


class NudeletedCrawler(KernelVideoSharingCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/videos/...",
        "Tags": "/tags/...",
        "Search": "/search/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://nudeleted.com")
    DOMAIN: ClassVar[str] = "nudeleted"
    FOLDER_DOMAIN: ClassVar[str] = "Nudeleted"
    NEXT_PAGE_SELECTOR: ClassVar[str] = "li.next > a"
    THUMBNAIL_SELECTOR: ClassVar[str] = "div.margin-fix > div.item a"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["videos", *_]:
                return await self.video(scrape_item)
            case ["search", query, *_]:
                return await self.search(scrape_item, query)
            case ["tags" as type_, name, *_]:
                return await self.collection(scrape_item, name, type_)
            case _:
                raise ValueError

    def _extract_upload_date(self, soup: BeautifulSoup) -> int | None:
        date_str: str = css.select(soup, 'meta[itemprop="uploadDate"]', "content")
        return self.parse_iso_date(date_str)
