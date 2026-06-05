from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import override

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    IMAGE = "img#img"
    ALBUM_IMAGES = "div#gdt.gt200 a"
    DATE = "td.gdt2"
    TITLE = "h1#gn"
    NEXT_PAGE = "td[onclick='document.location=this.firstChild.href']:-soup-contains('>') a"


class EHentaiCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/g/...",
        "File": "/s/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://e-hentai.org/")
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    DOMAIN: ClassVar[str] = "e-hentai"
    FOLDER_DOMAIN: ClassVar[str] = "E-Hentai"

    @override
    @staticmethod
    def __db_path__(url: AbsoluteHttpURL, /) -> str:
        return url.path.partition("/keystamp")[0]

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["g", _, gallery_id]:
                return await self.gallery(scrape_item, gallery_id)
            case ["s", _, _]:
                return await self.image(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def gallery(self, scrape_item: ScrapeItem, gallery_id: str) -> None:
        title: str = ""
        scrape_item.url = scrape_item.url.with_query(None)
        async for soup in self.web_pager(scrape_item.url):
            if not title:
                title = self.create_title(css.select_text(soup, Selector.TITLE))
                date_str: str = css.select_text(soup, Selector.DATE)
                title = self.create_title(title, gallery_id)
                scrape_item.setup_as_album(title, album_id=gallery_id)
                scrape_item.uploaded_at = self.parse_iso_date(date_str)

            for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.ALBUM_IMAGES):
                self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        link: str = css.select(soup, Selector.IMAGE, "src")
        src = self.parse_url(link)
        _, ext = self.get_filename_and_ext(src.name)
        filename = self.create_custom_filename(scrape_item.url.name, ext)
        await self.handle_file(src, scrape_item, src.name, ext, custom_filename=filename)
