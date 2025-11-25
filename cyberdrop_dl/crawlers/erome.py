from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import open_graph
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class Selector:
    ALBUM = "a.album-link"
    IMAGES = ".media-group img.img-front"
    VIDEOS = ".media-group .video video > source"
    MEDIA = f"{IMAGES}, {VIDEOS}"
    NEXT_PAGE = 'a[rel="next"]'


class EromeCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/a/<album_id>",
        "Profile": "/<name>",
        "Search": "/search?q=<query>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.erome.com")
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    DOMAIN: ClassVar[str] = "erome"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["a", album_id, *_]:
                return await self.album(scrape_item, album_id)
            case ["search", *_] if query := scrape_item.url.query.get("q"):
                return await self.search(scrape_item, query)
            case [name]:
                await self.profile(scrape_item, name)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def profile(self, scrape_item: ScrapeItem, name: str) -> None:
        title = self.create_title(name)
        scrape_item.setup_as_profile(title)
        await self.crawl_children(scrape_item, Selector.ALBUM)

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        title = self.create_title(f"{query} [search]")
        scrape_item.setup_as_album(title)
        await self.crawl_children(scrape_item, Selector.ALBUM)

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        results = await self.get_album_results(album_id)
        soup = await self.request_soup(scrape_item.url)
        name = open_graph.title(soup).removesuffix("- EroMe")
        title = self.create_title(name, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        for _, link in self.iter_tags(soup, Selector.MEDIA, "src", results=results):
            self.create_task(self.direct_file(scrape_item, link))
            scrape_item.add_children()


class EromeFanCrawler(EromeCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/a/<album_id>",
        "Profile": "/a/category/<name>",
        "Search": "/search/<query>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://erome.fan")
    DOMAIN: ClassVar[str] = "erome.fan"
    FOLDER_DOMAIN: ClassVar[str] = "Erome.fan"
    NEXT_PAGE_SELECTOR: ClassVar[str] = "a.next"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["a", "category", name, *_]:
                await self.profile(scrape_item, name)
            case ["a", album_id, *_]:
                return await self.album(scrape_item, album_id)
            case ["search", query, *_]:
                return await self.search(scrape_item, query)
            case _:
                raise ValueError
