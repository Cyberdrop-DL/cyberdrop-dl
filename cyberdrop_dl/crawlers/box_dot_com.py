from __future__ import annotations

import contextlib
import dataclasses
import itertools
from collections import deque
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, TypedDict, override

from typing_extensions import AsyncGenerator, ReadOnly

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Iterable

    from cyberdrop_dl.url_objects import ScrapeItem

APP_URL = AbsoluteHttpURL("https://app.box.com")


class BoxDotComCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = (APP_URL.host,)
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File or Folder": (
            "/s?sh=<share_name>",
            "/s/<share_name>",
        ),
        "Embedded File or Folder": (
            "/embed/s?sh=<share_name>",
            "/embed_widget/s?sh=<share_name>",
        ),
    }
    DOMAIN: ClassVar[str] = "box.com"
    FOLDER_DOMAIN: ClassVar[str] = "Box"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.box.com")

    def __post_init__(self) -> None:
        self.api: BoxDotComAPI = BoxDotComAPI.from_crawler(self)

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["embed_widget" | "embed_widget", *_] if share_name := url.query.get("sh"):
                return APP_URL / "s" / share_name
            case ["shared" | "embed_widget" | "embed_widget", share_name]:
                return APP_URL / "s" / share_name
            case _:
                return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["s", share_name]:
                await self.share(scrape_item, share_name)
            case ["s"] if share_name := scrape_item.url.query.get("sh"):
                await self.share(scrape_item, share_name)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def share(self, scrape_item: ScrapeItem, share_name: str) -> None:
        share = await self.api.share(share_name)
        if share.type == "file":
            file = await self.api.file(share.id, share.code)
            scrape_item.url = file.url
            await self._file(scrape_item, file)
            return

        folder, get_nodes = await self.api.folder(share.id, share.code)
        scrape_item.setup_as_album(self.create_title(folder.name, folder.share), album_id=folder.share)
        scrape_item.url = folder.url
        await self._walk_nodes(scrape_item, folder, get_nodes)

    async def _walk_nodes(
        self,
        scrape_item: ScrapeItem,
        folder: Folder,
        get_nodes: AsyncGenerator[Iterable[Node]],
    ) -> None:
        sleep = aio.periodic_sleep(100)
        subfolders: deque[int] = deque()

        while True:
            async with contextlib.aclosing(get_nodes) as pages, self.new_task_group(folder.url) as tg:
                async for nodes in pages:
                    for node in nodes:
                        if node["type"] == "folder":
                            subfolders.append(node["id"])
                            continue

                        if node["type"] != "file":
                            self.log.warning("Unknown node type: %s", node)
                            continue

                        file = File.from_node(node, folder.share)
                        new_item = scrape_item.create_child(file.url)
                        new_item.append_folders(*folder.path.parts[1:])
                        tg.create_task(self._file(new_item, file))
                        scrape_item.add_children()
                        await sleep()

            if not subfolders:
                break

            folder, get_nodes = await self.api.folder(subfolders.popleft(), folder.share)

    @error_handling_wrapper
    async def _file(self, scrape_item: ScrapeItem, file: File) -> None:
        filename, ext = self.get_filename_and_ext(file.name)
        scrape_item.uploaded_at = file.date
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            file.name,
            ext,
            custom_filename=filename,
            debrid_link=file.dl_url,
        )


class BoxDotComAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = APP_URL / "app-api/enduserapp"

    async def share(self, name: str) -> ShareItem:
        url = (self.ENTRYPOINT / "shared-item").with_query(sharedName=name)
        resp = await self.request_json(url)
        return ShareItem(id=resp["itemID"], code=resp["sharedName"], type=resp["itemType"])

    async def file(self, file_id: int, share_name: str) -> File:
        url = (self.ENTRYPOINT / f"item/f_{file_id}").with_query(preview="true")
        resp = await self.request_json(url, headers={"X-Box-EndUser-API": f"sharedName={share_name}"})
        return File.from_node(_normalize_node(resp["items"][0]), share_name)

    async def folder(self, folder_id: int, share_name: str) -> tuple[Folder, AsyncGenerator[map[Node]]]:
        url = (self.ENTRYPOINT / "shared-folder").with_query(folderID=folder_id)
        headers = {"X-Box-EndUser-API": f"sharedName={share_name}"}
        resp = await self.request_json(url, headers=headers)
        page_count: int = resp["pageCount"]

        async def nodes() -> AsyncGenerator[map[Node]]:
            nonlocal resp
            for page in itertools.count(1):
                yield map(_normalize_node, resp["items"])
                if page >= page_count:
                    break
                resp = await self.request_json(url.update_query(page=page), headers=headers)

        return Folder.parse(resp, share_name), nodes()


class Node(TypedDict):
    name: str
    type: ReadOnly[Literal["file", "folder"]]
    id: int
    typed_id: str
    date: int
    parent_id: int


@dataclasses.dataclass(slots=True, frozen=True)
class ShareItem:
    id: int
    code: str
    type: Literal["file", "folder"]


@dataclasses.dataclass(slots=True, frozen=True)
class File:
    id: int
    name: str
    typed_id: str
    date: int
    share: str

    @classmethod
    def from_node(cls, node: Node, share: str) -> Self:
        assert node["type"] == "file"
        return deserialize(cls, node, share=share)

    @property
    def url(self) -> AbsoluteHttpURL:
        return APP_URL / "s" / self.share / "file" / str(self.id)

    @property
    def dl_url(self) -> AbsoluteHttpURL:
        return (APP_URL / "index.php").with_query(
            shared_name=self.share, file_id=self.typed_id, rm="box_download_shared_file"
        )


@dataclasses.dataclass(slots=True, frozen=True)
class Folder:
    id: int
    name: str
    share: str
    path: PurePosixPath

    @property
    def url(self) -> AbsoluteHttpURL:
        return APP_URL / "s" / self.share / f"folder/{self.id}"

    @classmethod
    def parse(cls, folder: dict[str, Any], share_name: str) -> Self:
        return cls(
            id=folder["currentFolderID"],
            name=folder["currentFolderName"],
            share=share_name,
            path=PurePosixPath(*(p["name"] for p in folder["path"])),
        )


def _normalize_node(node: dict[str, Any]) -> Node:
    return {
        "name": node["name"],
        "type": node["type"],
        "id": node["id"],
        "typed_id": node["typedID"],
        "date": node.get("contentUpdated") or node["date"],
        "parent_id": node["parentFolderID"],
    }
