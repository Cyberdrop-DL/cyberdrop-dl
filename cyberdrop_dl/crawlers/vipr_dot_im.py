from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class ViprImCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Image": "/<id>",
        "Direct Image": "/i/.../<slug>",
        "Thumbnail": "/th/.../<slug>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vipr.im")
    DOMAIN: ClassVar[str] = "vipr.im"
    FOLDER_DOMAIN: ClassVar[str] = "Vipr.im"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_]:
                return await self.image(scrape_item)
            case _:
                raise ValueError

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["th" | "i", _, slug, *_]:
                return cls.PRIMARY_URL / Path(slug).stem
            case _:
                return url

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        link_str: str = css.select(soup, "div#body a > img", "src")
        await self.direct_file(scrape_item, self.parse_url(link_str))
