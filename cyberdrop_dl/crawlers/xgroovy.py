from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._fluid_player import FluidPlayerCrawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import open_graph
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedPaths
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class Selectors:
    ALBUM = "div.swiper-slide > a, a#main_image_holder"


_SELECTORS = Selectors()


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
        "Images": (
            "/<category>/photos/<photo_id>/...",
            "/photos/<photo_id>/...",
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
            case [*_, "photos", album_id, _]:
                return await self.album(scrape_item, album_id)
            case [*_, "contents", "albums", "sources", _, _, _]:
                return await self.direct_file(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        if not (title := open_graph.get_title(soup)):
            raise ScrapeError(401, "Could not find album title")
        title = self.create_title(title, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)
        for _, url in self.iter_tags(soup, _SELECTORS.ALBUM):
            await self.direct_file(scrape_item, url)
            scrape_item.add_children()
