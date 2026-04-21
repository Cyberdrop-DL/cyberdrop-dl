from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._fluid_player import FluidPlayerCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import error_handling_wrapper, open_graph

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedPaths
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    IMAGES = "a#main_image_holder, .swiper-wrapper .swiper-slide a"


class AnySexCrawler(FluidPlayerCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/video/<video_id>/...",
        "Album": "/photos/<album_id>/...",
        "Photo Search": "/photos/search/...",
        "Search": "/search/...",
    }
    DOMAIN: ClassVar[str] = "anysex"
    FOLDER_DOMAIN: ClassVar[str] = "AnySex"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://anysex.com")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [*_, "video", video_id, _]:
                return await self.video(scrape_item, video_id)
            case ["contents", _, *_]:
                return await self.direct_file(scrape_item)
            case ["photos", "search", *_] if query := scrape_item.url.query.get("q"):
                query = query.replace("-", " ")
                return await self.photo_search(scrape_item, query)
            case [*_, "photos", album_id, _]:
                return await self.album(scrape_item, album_id)
            case ["search" as type_, *_] if query := scrape_item.url.query.get("q"):
                query = query.replace("-", " ")
                return await self.collection(scrape_item, type_, query)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def photo_search(self, scrape_item: ScrapeItem, query: str) -> None:
        scrape_item.setup_as_album(self.create_title(query))
        async for soup in self.web_pager(scrape_item.url):
            for _, new_scrape_item in self.iter_children(scrape_item, soup, ".item > a"):
                self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        name = open_graph.title(soup)
        title = self.create_title(f"{name} [album]")
        scrape_item.setup_as_album(title, album_id=album_id)
        for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.IMAGES):
            self.create_task(self.run(new_scrape_item))
