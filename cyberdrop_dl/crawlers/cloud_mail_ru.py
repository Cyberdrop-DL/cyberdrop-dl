from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.utilities import get_text_between

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class CloudMailRuCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Video": "videos"}
    DOMAIN: ClassVar[str] = "cloud.mail.ru"
    FOLDER_DOMAIN: ClassVar[str] = DOMAIN
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://cloud.mail.ru")
    SKIP_PRE_CHECK: ClassVar[bool] = True

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["public", a, b]:
                return await self.file(scrape_item, path=f"{a}/{b}")
            case _:
                raise ValueError

    async def _get_dl_link(self, path: str) -> AbsoluteHttpURL:
        web_url = self.PRIMARY_URL / "public" / path
        html = await self.request_text(
            web_url,
            max_field_size=15_000,  # They send a really long header value for "Content-Security-Policy-Report-Only"
        )
        data = get_text_between(html, '"weblink_get":', "},")
        base_url = self.parse_url(json.loads(data + "}")["url"])
        return base_url / path

    async def file(self, scrape_item: ScrapeItem, path: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        dl_link = await self._get_dl_link(path)
        api_url = (self.PRIMARY_URL / "api/v4/public/list").with_query(
            weblink=path,
            sort="name",
            order="asc",
            offset=0,
            limit=500,
            version=4,
        )
        file = await self.request_json(api_url)
        filename, ext = self.get_filename_and_ext(file["name"])
        scrape_item.possible_datetime = file["mtime"]
        await self.handle_file(
            scrape_item.url, scrape_item, file["name"], ext, debrid_link=dl_link, custom_filename=filename
        )
