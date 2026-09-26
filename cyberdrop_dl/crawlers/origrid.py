from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class OrigridCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"File": "/d/<file_id>"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://origrid.io")
    DOMAIN: ClassVar[str] = "origrid"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["d", _]:
                await self.file(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        name = css.select_text(soup, "[data-origrid=name]")
        src = self.parse_url(css.select(soup, "a[data-origrid=download]", "href"))
        filename, ext = self.get_filename_and_ext(name)
        await self.handle_file(scrape_item.url, scrape_item, filename, ext, debrid_link=src)
