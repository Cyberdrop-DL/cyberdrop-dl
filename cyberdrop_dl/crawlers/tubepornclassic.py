from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._tubecorporate import TubeCorporateCrawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedPaths
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class TubePornClassicCrawler(TubeCorporateCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/videos/...",
    }
    DOMAIN: ClassVar[str] = "tubepornclassic"
    FOLDER_DOMAIN: ClassVar[str] = "TubePornClassic"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://tubepornclassic.com")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["videos", video_id, _]:
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError
