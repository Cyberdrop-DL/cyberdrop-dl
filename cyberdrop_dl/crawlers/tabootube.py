from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._kvs import KernelVideoSharingCrawler, _extract_upload_date
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.crawlers.crawler import SupportedPaths


class TabooTubeCrawler(KernelVideoSharingCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Video": "/video/..."}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.tabootube.xxx")
    DOMAIN: ClassVar[str] = "tabootube"
    FOLDER_DOMAIN: ClassVar[str] = "TabooTube"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video", *_]:
                return await self.video(scrape_item)
            case _:
                raise ValueError

    def _extract_upload_date(self, soup: BeautifulSoup) -> float | None:
        if date_str := _extract_upload_date(soup):
            return self.parse_iso_date(date_str.replace(" T", "T"))
