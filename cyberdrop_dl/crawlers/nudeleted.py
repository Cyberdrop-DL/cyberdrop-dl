from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._kvs import KernelVideoSharingCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedPaths


class NudeletedCrawler(KernelVideoSharingCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Video": "/videos/..."}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://nudeleted.com")
    DOMAIN: ClassVar[str] = "nudeleted"
    FOLDER_DOMAIN: ClassVar[str] = "Nudeleted"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["videos", *_]:
                return await self.video(scrape_item)
            case _:
                raise ValueError
