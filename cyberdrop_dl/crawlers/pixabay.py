from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.network.http import HTTPConfig
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import json_ld
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


@HTTPConfig(impersonate=True)
class PixabayCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Music": "/music/<slug>-<id>",
        "Photos": "/photos/<slug>-<id>",
        "GIFs": "/gifs/<slug>-<id>",
        "Illustrations": "/illustrations/<slug>-<id>",
        "Sound-effects": "/sound-effects/<slug>-<id>",
        "Videos": "/videos/<slug>-<id>",
        "3D models": "/3d-models/<slug>-<id>",
        "Vectors": "/vectors/<slug>-<id>",
    }
    DOMAIN: ClassVar[str] = "pixabay"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pixabay.com")

    def __post_init__(self) -> None:
        self.update_cookies({"is_human": 1})

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [
                "music" | "photos" | "illustrations" | "sound-effects" | "videos" | "gifs" | "3d-models" | "vectors",
                slug,
            ]:
                item_id = slug.rpartition("-")[-1]
                await self.file(scrape_item, item_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, file_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url, impersonate=True)
        elem = json_ld.find_elem(soup, "contentUrl")
        scrape_item.uploaded_at = self.parse_iso_date(elem["uploadDate"])
        src = self.parse_url(elem["contentUrl"])
        name = src.query.get("filename") or src.name

        _, ext = self.get_filename_and_ext(name, mime_type=elem.get("encodingFormat"))
        await self.handle_file(
            src,
            scrape_item,
            name,
            ext,
            custom_filename=self.create_custom_filename(name, ext, file_id=file_id),
            thumbnail=elem.get("thumbnailUrl"),
        )
