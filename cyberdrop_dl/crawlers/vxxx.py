from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._tubecorporate import TubeCorporateCrawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedPaths
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class VXXXCrawler(TubeCorporateCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/video-...",
    }
    DOMAIN: ClassVar[str] = "vxxx"
    FOLDER_DOMAIN: ClassVar[str] = "VXXX"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vxxx.com")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [video_path] if video_path.startswith("video-"):
                video_id = video_path.split("-")[1]
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError
