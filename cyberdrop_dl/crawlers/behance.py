from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper

IMAGE_SELECTOR = "img.ImageModuleContent-mainImage-IG1"


class BehanceCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Gallery": "/gallery/<gallery_id>/<gallery_name>",
        "Image": "/gallery/<gallery_id>/<gallery_name>/modules/<module_id>",
        "Profile": "/<user_name>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.behance.net")
    DOMAIN: ClassVar[str] = "behance.net"
    FOLDER_DOMAIN: ClassVar[str] = "Behance"

    async def async_startup(self) -> None:
        # Load initial cookies by requesting the primary URL
        await self.request_soup(self.PRIMARY_URL, impersonate=True)
        self.update_cookies({"originalReferrer": "", "ilo0": "true", "ilo1": "true"})

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["gallery", gallery_id, gallery_name, "modules", _]:
                return await self.image(scrape_item)
            case ["gallery", gallery_id, gallery_name]:
                return await self.gallery(scrape_item, gallery_id, gallery_name)
            case [user_name]:
                return await self.profile(scrape_item, user_name)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def gallery(self, scrape_item: ScrapeItem, gallery_id: str, gallery_name: str) -> None:
        pass  # Implementation of gallery fetching logic goes here

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        link_str: str = css.select(soup, IMAGE_SELECTOR, "src")
        link = self.parse_url(link_str).with_query(None)
        await self.direct_file(scrape_item, link)

    @error_handling_wrapper
    async def profile(self, scrape_item: ScrapeItem, user_name: str) -> None:
        pass  # Implementation of profile fetching logic goes here
