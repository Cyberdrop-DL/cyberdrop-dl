from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class File(NamedTuple):
    name: str
    url: AbsoluteHttpURL
    size: int


class RootzCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File": (
            "/d/<file_id>",
            "/file/<file_id>",
        )
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.rootz.so")
    DOMAIN: ClassVar[str] = "rootz.so"
    _RATE_LIMIT: ClassVar[RateLimit] = 100, 60
    _API_ENTRYPOINT: ClassVar[AbsoluteHttpURL] = PRIMARY_URL / "api/files"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["d" | "file", short_code]:
                return await self.file(scrape_item, short_code)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, file_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        is_short_code = "-" not in file_id
        api_url = self._API_ENTRYPOINT / ("download-by-short" if is_short_code else "download") / file_id
        name, url, _ = await self._request_file(api_url)
        filename, ext = self.get_filename_and_ext(name)
        await self.handle_file(scrape_item.url, scrape_item, name, ext, debrid_link=url, custom_filename=filename)

    async def _request_file(self, api_url: AbsoluteHttpURL) -> File:
        data: dict[str, Any] = (await self.request_json(api_url))["data"]
        return File(
            name=data.get("filename") or data["fileName"],
            url=self.parse_url(data["url"]),
            size=data["size"],
        )


class RanozCrawler(RootzCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://ranoz.gg")
    DOMAIN: ClassVar[str] = "ranoz.gg"
    FOLDER_DOMAIN: ClassVar[str] = "Ranoz.gg"
    OLD_DOMAINS = ("qiwi.gg",)
    _FILE_SERVER = AbsoluteHttpURL("https://st7.ranoz.gg")
    _API_ENTRYPOINT = PRIMARY_URL / "api/v1/files"

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, file_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        name, *_ = await self._request_file(self._API_ENTRYPOINT / file_id)
        url = self._FILE_SERVER / f"{file_id}-{name}"
        filename, ext = self.get_filename_and_ext(name)
        await self.handle_file(scrape_item.url, scrape_item, name, ext, debrid_link=url, custom_filename=filename)
