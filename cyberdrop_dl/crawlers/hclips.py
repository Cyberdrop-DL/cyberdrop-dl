from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._tubecorporate import TubeCorporateCrawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedDomains, SupportedPaths
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class HClipsCrawler(TubeCorporateCrawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = ("privatehomeclips.com",)
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/videos/...",
    }
    DOMAIN: ClassVar[str] = "hclips"
    FOLDER_DOMAIN: ClassVar[str] = "HClips"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://hclips.com")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["videos" | "embed", video_id, *_]:
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError
