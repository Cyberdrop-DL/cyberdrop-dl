from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths, auto_task_id
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, json_ld, unique
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


@final
class Selector:
    ALBUM_TITLE = "h1.album-page-title"
    DATE = "span.date-time"
    IMAGES = "#album-images .image-block[data-key]"
    IMAGE = ".main-image-wrapper"


class PimpAndHostCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/album/<album_id>",
        "Image": "/image/<image_id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pimpandhost.com")
    NEXT_PAGE_SELECTOR: ClassVar[str] = "li[class=next] a"
    DOMAIN: ClassVar[str] = "pimpandhost"
    FOLDER_DOMAIN: ClassVar[str] = "PimpAndHost"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["album", album_id, *_]:
                await self.album(scrape_item, album_id)
            case ["image", _]:
                await self.image(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup, pages = await aio.peek_first(self.web_pager(scrape_item.url))
        title = self.create_title(css.select_text(soup, Selector.ALBUM_TITLE), album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            async for soup in pages:
                for image_id in unique(css.iselect(soup, Selector.IMAGES, "data-key")):
                    new_item = scrape_item.create_child(self.PRIMARY_URL / "image" / image_id)
                    tg.create_task(self._image_task(new_item))
                    scrape_item.add_children()
                    await sleep()

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        src = self.parse_url(css.select(soup, Selector.IMAGE, "data-src"))
        scrape_item.uploaded_at = json_ld.date_published(soup)
        filename, ext = self.get_filename_and_ext(src.name)
        await self.handle_file(src, scrape_item, filename, ext)

    _image_task = auto_task_id(image)
