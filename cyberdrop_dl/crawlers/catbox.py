from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class CatboxCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = (
        "litter.catbox.moe",
        "files.catbox.moe",
        "litter.fatbox.moe",
        "files.fatbox.moe",
    )
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Direct links": ""}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://catbox.moe")
    DOMAIN: ClassVar[str] = "catbox.moe"
    FOLDER_DOMAIN: ClassVar[str] = "Catbox"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if scrape_item.url.host not in self.SUPPORTED_DOMAINS:
            raise ValueError
        await self.direct_file(scrape_item, assume_ext=".zip")
