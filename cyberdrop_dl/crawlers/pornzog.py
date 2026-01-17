from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class Selectors:
    EMBED_IFRAME = "div.fluid-width-video-wrapper > iframe"


PRIMARY_URL = AbsoluteHttpURL("https://pornzog.com")


class PornZogCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/video/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "pornzog"
    FOLDER_DOMAIN: ClassVar[str] = "PornZog"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video", _, _]:
                return await self.video(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)
        iframe = css.select(soup, Selectors.EMBED_IFRAME)
        external_url = self.parse_url(css.get_attr(iframe, "src"))
        new_scrape_item = scrape_item.create_child(external_url)
        return self.handle_external_links(new_scrape_item)
