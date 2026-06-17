from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._kvs import KernelVideoSharingCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import css, error_handling_wrapper

if TYPE_CHECKING:
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
            case ["tags" | "search", *_]:
                return await self.collection(scrape_item, scrape_item.url.parts[-1], "tags")
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return
        soup = await self.request_soup(scrape_item.url)
        date_str: str = css.select(soup, 'meta[itemprop="uploadDate"]', "content")
        scrape_item.uploaded_at = self.parse_iso_date(date_str)
        await super().video(scrape_item, soup)
