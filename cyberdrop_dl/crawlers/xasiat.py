from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._kvs import KernelVideoSharingCrawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL, ScrapeItem

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedPaths


class XasiatCrawler(KernelVideoSharingCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/albums/<id>/<name>",
        "Images": "/get_image/...",
        "Videos": "/videos/<id>/<name>",
    }

    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.xasiat.com")
    DOMAIN: ClassVar[str] = "xasiat"
    DEFAULT_TRIM_URLS: ClassVar[bool] = False

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["albums", album_id, _, *_]:
                return await self.album(scrape_item, album_id)
            case ["videos", _, _, *_]:
                return await self.video(scrape_item)
            case ["get_image", _, *_]:
                return await self.direct_file(scrape_item)
            case _:
                raise ValueError
