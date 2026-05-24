"""
https://archive.org/developers/bots.html#user-agent-requirements
https://archive.org/developers/metadata-schema/index.html#public-files-fields
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.constants import CDL_USER_AGENT
from cyberdrop_dl.crawlers.crawler import API, Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import DictDataclass, error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from cyberdrop_dl.url_objects import ScrapeItem


class ArchiveOrgCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Item": (
            "/details/<identifier>",
            "/download/<identifier>",
        ),
        "Files": (
            "/details/<identifier>/<subpath>",
            "/download/<identifier>/<subpath>",
        ),
    }

    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://archive.org")
    DOMAIN: ClassVar[str] = "archive.org"
    _RATE_LIMIT: ClassVar[RateLimit] = 3, 1

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if scrape_item.url.host == "web.archive.org":
            raise ValueError

        match scrape_item.url.parts[1:]:
            case ["details" | "download", identifier, *rest]:
                base_path = "/".join(rest) if rest else None
                return await self.item(scrape_item, identifier, base_path)
            case _:
                raise ValueError

    def __post_init__(self) -> None:
        self.api: ArchiveOrgAPI = ArchiveOrgAPI(self)

    @error_handling_wrapper
    async def item(self, scrape_item: ScrapeItem, identifier: str, base_path: str | None = None) -> None:
        identifier = identifier.replace("+", " ")
        item = await self.api.item(identifier)
        if item.is_collection:
            raise ScrapeError(422, "Collections are not supported")

        scrape_item.setup_as_album(self.create_title(item.title), album_id=identifier)

        for file in _filter_files(base_path, item.files):
            url = self.PRIMARY_URL / "details" / identifier / file.path
            new_item = scrape_item.create_child(url)
            self.create_task(self._file(new_item, identifier, file))
            scrape_item.add_children()

    @error_handling_wrapper
    async def _file(self, scrape_item: ScrapeItem, identifier: str, file: File) -> None:
        url = self.PRIMARY_URL / "download" / identifier / file.path
        if await self.check_complete_by_hash(url, "md5", file.md5):
            return

        if file.private:
            raise ScrapeError(401)

        for part in Path(file.path).parts[:-1]:
            scrape_item.add_to_parent_title(part)

        scrape_item.uploaded_at = file.mtime
        filename, ext = self.get_filename_and_ext(file.name)
        await self.handle_file(url, scrape_item, file.name, ext, custom_filename=filename, metadata=file)


class ArchiveOrgAPI(API):
    async def metadata(self, identifier: str) -> dict[str, Any]:
        return await self._request(self.crawler.PRIMARY_URL / "metadata" / identifier)

    async def item(self, identifier: str) -> Item:
        metadata = await self.metadata(identifier)
        return Item.from_dict(
            metadata["metadata"],
            files=tuple(_parse_files(metadata["files"])),
        )

    async def _request(self, url: AbsoluteHttpURL) -> dict[str, Any]:
        resp = await self.request_json(url, headers={"User-Agent": CDL_USER_AGENT, "Accept-Encoding": "deflate, gzip"})
        if not resp:
            raise ScrapeError(404)
        if error := resp.get("error"):
            raise ScrapeError(422, str(error))
        return resp


@dataclasses.dataclass(slots=True)
class Item(DictDataclass):
    identifier: str
    mediatype: str
    title: str
    files: tuple[File, ...]

    @property
    def is_collection(self) -> bool:
        return self.mediatype == "collection"


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
    private: bool = False

    path: str = dataclasses.field(init=False)
    suffix: str = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        # Name is actually the full relative path to this file ex: /photos/feb/image.png
        self.path = self.name
        path = Path(self.name)
        self.name, self.suffix = path.name, path.suffix
        self.mtime, self.size = int(self.mtime), int(self.size)
        self.private = str(self.private).lower() == "true"


def _filter_files(basepath: str | None, files: Iterable[File]) -> Iterable[File]:
    return (f for f in files if _is_subpath(basepath, f.path))


def _is_subpath(basepath: str | None, path: str) -> bool:
    if not basepath:
        return True

    return path.startswith(basepath) or path.replace(" ", "+").startswith(basepath)


def _parse_files(files: list[dict[str, Any]]) -> Generator[File]:
    for file_info in files:
        if "mtime" not in file_info:
            continue

        file = File.from_dict(file_info)
        if file.suffix not in {".torrent", ".sqlite"}:
            yield file
