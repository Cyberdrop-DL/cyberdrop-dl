from __future__ import annotations

import random
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import open_graph
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem

PRIMARY_URL = AbsoluteHttpURL("https://filester.me/")
DOWNLOAD_API_ENTRYPOINT = "https://filester.me/api/public/download"


class FilesterMeCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"File": "/d/<slug>"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "filester.me"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["d", slug, *_]:
                return await self.file(scrape_item, slug)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, slug: str) -> None:
        soup = await self.request_soup(scrape_item.url, impersonate=True)
        file_name = open_graph.get_title(soup)
        token = await self._get_download_token(slug)
        cdn = self._choose_cdn()
        final_url = AbsoluteHttpURL(f"{cdn}{token}?download=true")
        filename, ext = self.get_filename_and_ext(file_name)
        await self.handle_file(
            scrape_item.url, scrape_item, filename, ext, debrid_link=final_url
        )

    def _choose_cdn(self) -> str:
        CDNS = [
            "https://cache1.filester.me",
            "https://cache6.filester.me",
        ]
        return random.choice(CDNS)

    async def _get_download_token(self, slug: str) -> str:
        data: dict[str, str] = await self.request_json(
            DOWNLOAD_API_ENTRYPOINT,
            method="POST",
            json={"file_slug": slug},
        )
        if not data.get("success"):
            raise ScrapeError(422)
        return data["download_url"]
