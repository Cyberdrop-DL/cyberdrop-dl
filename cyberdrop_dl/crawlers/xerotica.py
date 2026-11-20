from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final, override

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths, URLConfig
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, open_graph
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


@final
class Selector:
    MODEL_NAME = "header h1"
    VIDEOS = "ul.list-collection .item-col a"
    NEXT_PAGE = "nav.nav-pagination a[rel=next]"


@URLConfig(trim=False)
class XeroticaCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/video/<slug>-<id>.html",
        "Model": "/model/<name>-<id>.html/...",
        "Search": "/search/<query>/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.xerotica.com")
    DOMAIN: ClassVar[str] = "xerotica"
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE

    @override
    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video", slug, *_] if "-" in slug:
                video_id = slug.rpartition("-")[-1].removesuffix(".html")
                await self.video(scrape_item, video_id)
            case ["models", slug, *_] if "-" in slug:
                await self.model(scrape_item)
            case ["search", query, *_]:
                await self.search(scrape_item, query)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        src = self.parse_url(css.select(soup, "video source", "src"))
        await self.handle_file(
            src,
            scrape_item,
            name := open_graph.title(soup),
            ext := ".mp4",
            custom_filename=self.create_custom_filename(name, ext, file_id=video_id),
            thumbnail=open_graph.get_image(soup),
        )

    @error_handling_wrapper
    async def model(self, scrape_item: ScrapeItem) -> None:
        soup, pages = await aio.peek_next(self.web_pager(scrape_item.url))
        name = css.select_text(soup, Selector.MODEL_NAME, decompose="span")
        scrape_item.setup_as_album(self.create_title(f"{name} [model]"))

        async for soup in pages:
            for new_item in self.iter_children(scrape_item, soup, Selector.VIDEOS):
                self.create_task(self.run(new_item, check_referer=True))

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        soup, pages = await aio.peek_next(self.web_pager(scrape_item.url))
        scrape_item.setup_as_album(self.create_title(f"{query} [search]"))

        async for soup in pages:
            for new_item in self.iter_children(scrape_item, soup, Selector.VIDEOS):
                self.create_task(self.run(new_item, check_referer=True))
