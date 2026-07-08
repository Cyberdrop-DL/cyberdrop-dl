from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    ALBUM_TITLE = "span.author-header__album-name"
    DATE = "span.date-time"
    FILES = 'a[class*="image-wrapper center-cropped im-wr"]'
    IMAGE = ".main-image-wrapper"


DATE_FORMAT = "%A, %B %d, %Y %I:%M:%S%p %Z"


class PimpAndHostCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Album": "/album/...", "Image": "/image/..."}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pimpandhost.com")
    NEXT_PAGE_SELECTOR: ClassVar[str] = "li[class=next] a"
    DOMAIN: ClassVar[str] = "pimpandhost"
    FOLDER_DOMAIN: ClassVar[str] = "PimpAndHost"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["album", album_id, *_]:
                return await self.album(scrape_item, album_id)
            case _:
                await self.image(scrape_item)

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup, pages = await aio.peek_first(self.web_pager(scrape_item.url))
        title_portion = css.select_text(soup, Selector.ALBUM_TITLE)
        title = self.create_title(title_portion, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        if date_tag := soup.select_one(Selector.DATE):
            scrape_item.uploaded_at = self.parse_date(css.attr(date_tag, "title"), DATE_FORMAT)

        async for soup in pages:
            for new_scrape_item in self.iter_children(scrape_item, soup, Selector.FILES):
                self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)

        link_str: str = css.select(soup, Selector.IMAGE, "data-src")
        link = self.parse_url(link_str)
        date_str: str = css.select(soup, Selector.DATE, "title")
        scrape_item.uploaded_at = self.parse_date(date_str, DATE_FORMAT)
        filename, ext = self.get_filename_and_ext(link.name)
        await self.handle_file(link, scrape_item, filename, ext)
