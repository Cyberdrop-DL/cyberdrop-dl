from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._tubecorporate import TubeCorporateCrawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedPaths
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class XMilfCrawler(TubeCorporateCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/video/...",
    }
    DOMAIN: ClassVar[str] = "xmilf"
    FOLDER_DOMAIN: ClassVar[str] = "XMilf"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://xmilf.com")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video", video_id, _]:
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError
