from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper, get_text_between

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class FuckingFastCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Direct links": "/<file_id>"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://fuckingfast.co")
    DOMAIN: ClassVar[str] = "fuckingfast.co"
    FOLDER_DOMAIN: ClassVar[str] = "FuckingFast"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_]:
                return await self.file(scrape_item)
            case _:
                raise ValueError

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        return super().transform_url(url).with_fragment(None)

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        name = css.page_title(soup)
        dl_link = get_text_between(str(soup), 'window.open("https:', ")").strip('"')
        link = self.parse_url(f"https:{dl_link}")
        filename, ext = self.get_filename_and_ext(name)
        await self.handle_file(scrape_item.url, scrape_item, name, ext, debrid_link=link, custom_filename=filename)
