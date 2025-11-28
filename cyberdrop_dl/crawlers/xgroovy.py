from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._fluid_player import FluidPlayerCrawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedPaths
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class XGroovyCrawler(FluidPlayerCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/<category>/videos/<video_id>/...",
            "/videos/<video_id>/...",
        ),
        "Gif": (
            "/<category>/gifs/<gif_id>/...",
            "/gifs/<gif_id>/...",
        ),
        "Search": (
            "/<category>/search/...",
            "/search/...",
        ),
        "Pornstar": (
            "/<category>/pornstars/<pornstar_id>/...",
            "/pornstars/<pornstar_id>/...",
        ),
        "Tag": (
            "/<category>/tags/...",
            "/tags/...",
        ),
        "Channel": (
            "/<category>/channels/...",
            "/channels/...",
        ),
    }
    DOMAIN: ClassVar[str] = "xgroovy"
    FOLDER_DOMAIN: ClassVar[str] = "XGroovy"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://xgroovy.com")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [*_, "videos" | "gifs", video_id, _]:
                return await self.video(scrape_item, video_id)
            case [*_, "pornstars" as type_, _]:
                return await self.collection(scrape_item, type_)
            case [*_, "categories" | "channels" | "search" | "tag" as type_, slug]:
                return await self.collection(scrape_item, type_, slug)
            case _:
                raise ValueError
