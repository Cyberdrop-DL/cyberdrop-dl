from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths, URLConfig, auto_task_id
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    IMAGE = "div[class=block-video] a img"
    CONTENT = "div[id=list_videos_common_videos_list_items] div a"


@URLConfig(trim=False)
class NudoStarTVCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Model": "/models/<name>",
        "Image": "/models/<name>/<img_id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://nudostar.tv")
    NEXT_PAGE_SELECTOR: ClassVar[str] = "li[class=next] a"
    DOMAIN: ClassVar[str] = "nudostar.tv"
    FOLDER_DOMAIN: ClassVar[str] = "NudoStarTV"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["models", _, _, *rest]:
                if rest:
                    await self.image(scrape_item)
                else:
                    await self.model(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def model(self, scrape_item: ScrapeItem) -> None:
        soup, pages = await aio.peek_next(self.web_pager(scrape_item.url))
        scrape_item.setup_as_album("")

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            async for soup in pages:
                for new_item in self.iter_children(scrape_item, soup, Selector.CONTENT):
                    tg.create_task(self._image_task(new_item))
                    await sleep()

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        scrape_item.setup_as_album(self.create_title(css.select_text(soup, ".headline").partition("/")[0]))
        src = self.parse_url(css.select(soup, Selector.IMAGE, "src"))
        await self.direct_file(scrape_item, src)

    _image_task = auto_task_id(image)
