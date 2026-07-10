from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, open_graph
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class CrazyShitCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/cnt/medias/<slug>",
        "Series": "/series/<name>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://crazyshit.com")
    DOMAIN: ClassVar[str] = "crazyshit"
    FOLDER_DOMAIN: ClassVar[str] = "CrazyShit"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["cnt", "medias", slug]:
                video_id = str(int(slug.partition("-")[0]))
                return await self.video(scrape_item, video_id)
            case ["series", _]:
                return await self.series(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        title = css.select_text(soup, "h1.title", strip=False)
        src = self.parse_url(css.select(soup, "video source", "src"))
        filename = self.create_custom_filename(title, ext := ".mp4", file_id=video_id)
        await self.handle_file(scrape_item.url, scrape_item, title, ext, custom_filename=filename, debrid_link=src)

    @error_handling_wrapper
    async def series(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)
        title = open_graph.title(soup)
        scrape_item.setup_as_album(self.create_title(title))
        sleep = aio.periodic_sleep(10)
        for new_item in self.iter_children(scrape_item, soup, ".row.tiles a.thumb"):
            self.create_eager_task(self.run(new_item))
            await sleep()
