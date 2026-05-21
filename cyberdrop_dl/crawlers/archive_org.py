"""
https://archive.org/developers/bots.html#user-agent-requirements
https://archive.org/developers/metadata-schema/index.html#public-files-fields
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.constants import CDL_USER_AGENT
from cyberdrop_dl.crawlers.crawler import Crawler, CrawlerAPI, RateLimit, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import DictDataclass, error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.url_objects import ScrapeItem


@dataclasses.dataclass(slots=True)
class File(DictDataclass):
    name: str
    source: str
    format: str
    mtime: int
    size: int
    md5: str
    crc32: str
    sha1: str


@dataclasses.dataclass(slots=True)
class Item(DictDataclass):
    identifier: str
    mediatype: str
    files: tuple[File, ...]
    title: str
    server: str
    addeddate: str


class ArchiveOrgCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Item": "/details/<identifier>",
    }

    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://archive.org")
    DOMAIN: ClassVar[str] = "archive.org"
    _RATE_LIMIT: ClassVar[RateLimit] = 3, 1

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["details", identifier]:
                return await self.item(scrape_item, identifier)
            case _:
                raise ValueError

    async def __async_post_init__(self) -> None:
        self.api: ArchiveOrgAPI = ArchiveOrgAPI(self)

    async def item(self, scrape_item: ScrapeItem, identifier: str) -> None:
        item = await self.api.item(identifier)
        scrape_item.setup_as_album(self.create_title(item.title))
        for file in item.files:
            self.create_task(self._file(scrape_item.copy(), file, item.identifier))
            scrape_item.add_children()

    @error_handling_wrapper
    async def _file(self, scrape_item: ScrapeItem, file: File, identifier: str) -> None:
        url = self.PRIMARY_URL / "download" / identifier / file.name
        if await self.check_complete_by_hash(url, "md5", file.md5):
            return

        scrape_item.uploaded_at = file.mtime
        filename, ext = self.get_filename_and_ext(file.name)
        await self.handle_file(url, scrape_item, file.name, ext, custom_filename=filename, metadata=file)


class ArchiveOrgAPI(CrawlerAPI):
    async def metadata(self, identifier: str) -> dict[str, Any]:
        return await self._request(self.crawler.PRIMARY_URL / "metadata" / identifier)

    async def item(self, identifier: str) -> Item:
        metadata = await self.metadata(identifier)
        return Item.from_dict(
            metadata["metadata"],
            server=metadata["server"],
            files=tuple(_parse_files(metadata["files"])),
        )

    async def _request(self, url: AbsoluteHttpURL) -> dict[str, Any]:
        resp = await self.request_json(url, headers={"User-Agent": CDL_USER_AGENT, "Accept-Encoding": "deflate, gzip"})
        if not resp:
            raise ScrapeError(404)
        if error := resp.get("error"):
            raise ScrapeError(422, str(error))
        return resp


def _parse_files(files: list[dict[str, Any]]) -> Generator[File]:
    for file_info in files:
        if file_info["source"] == "derivative" or "mtime" not in file_info:
            continue

        yield File.from_dict(file_info, mtime=int(file_info["mtime"]), size=int(file_info["size"]))
