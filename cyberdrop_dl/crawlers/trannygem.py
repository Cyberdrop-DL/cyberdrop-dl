from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers._kvs import KernelVideoSharingCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem


class TrannyGemCrawler(KernelVideoSharingCrawler, ensure_trailing_slash=True):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.trannygem.com")
    DOMAIN: ClassVar[str] = "trannygem"
    FOLDER_DOMAIN: ClassVar[str] = "TrannyGem"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["videos", *_]:
                return await self.video(scrape_item)
            case _:
                raise ValueError
