from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


_PRIMARY_URL = AbsoluteHttpURL("https://www.rootz.so")
_API_ENTRYPOINT = _PRIMARY_URL / "api/files"


class RootzCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"File": "/d/<file_id>"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = _PRIMARY_URL
    DOMAIN: ClassVar[str] = "rootz.so"
    _RATE_LIMIT: ClassVar[RateLimit] = 100, 60

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["d", short_code]:
                return await self.file(scrape_item, short_code)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, file_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        is_short_code = "-" not in file_id
        api_url = _API_ENTRYPOINT / ("download-by-short" if is_short_code else "download") / file_id
        resp: dict[str, Any] = (await self.request_json(api_url))["data"]
        name: str = resp["fileName"]
        url = self.parse_url(resp["url"])
        filename, ext = self.get_filename_and_ext(name)
        await self.handle_file(scrape_item.url, scrape_item, name, ext, debrid_link=url, custom_filename=filename)
