from __future__ import annotations

import asyncio
import dataclasses
import json
from collections import defaultdict
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, TypedDict, override

from typing_extensions import ReadOnly

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cyberdrop_dl.url_objects import ScrapeItem

APP_URL = AbsoluteHttpURL("https://app.box.com")


class BoxDotComCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = (APP_URL.host,)
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File or Folder": (
            "/s?sh=<share_code>",
            "/s/<share_code>",
        ),
        "Embedded File or Folder": (
            "app.box.com/embed/s?sh=<share_code>",
            "app.box.com/embed_widget/s?sh=<share_code>",
        ),
    }
    DOMAIN: ClassVar[str] = "box.com"
    FOLDER_DOMAIN: ClassVar[str] = "Box"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.box.com")

    def __post_init__(self) -> None:
        self.api: BoxDotComAPI = BoxDotComAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["s", share_code]:
                await self.share(scrape_item, share_code)
            case ["s"] if share_code := scrape_item.url.query.get("sh"):
                await self.share(scrape_item, share_code)
            case _:
                raise ValueError

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["embed_widget" | "embed_widget", *_] if share_code := url.query.get("sh"):
                return APP_URL / "s" / share_code
            case ["shared" | "embed_widget" | "embed_widget", share_code]:
                return APP_URL / "s" / share_code
            case _:
                return url

    @error_handling_wrapper
    async def share(self, scrape_item: ScrapeItem, share_code: str) -> None:
        share = await self.api.share(share_code)
        if isinstance(share, File):
            scrape_item.url = share.url
            await self._file(scrape_item, share)
            return

        await self._filesystem(scrape_item, share)

    async def _filesystem(self, scrape_item: ScrapeItem, fs: FileSystem) -> None:
        scrape_item.setup_as_album(self.create_title(fs.name, fs.share_code), album_id=fs.share_code)
        scrape_item.url = APP_URL / "s" / fs.share_code / f"folder/{fs.id}"

        sleep = aio.periodic_sleep(100)
        async with self.new_task_group(scrape_item) as tg:
            for path, node in fs.nodes.items():
                if node["type"] != "file":
                    continue

                file = File.from_node(node, fs.share_code)
                new_item = scrape_item.create_child(file.url)
                new_item.append_folders(*path.parts)
                tg.create_task(self._file(new_item, file))
                scrape_item.add_children()
                await sleep()

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
            debrid_link=self.api.src(file),
        )


class BoxDotComAPI(API):
    async def share(self, share_code: str) -> File | FileSystem:
        url = self.PRIMARY_URL / "s" / share_code
        data = await self.request_stream_data(url)
        return await asyncio.to_thread(_parse_share, data)

    async def request_stream_data(self, url: AbsoluteHttpURL) -> str:
        async with self.request(url) as resp:
            if "file or folder link has been removed" in await resp.text():
                raise ScrapeError(410)

            soup = await resp.soup()

        js_text: str = css.select_text(soup, "script:-soup-contains('Box.postStreamData')")
        return "{" + extr_text(js_text, "{", "};") + "}"

    def src(self, file: File) -> AbsoluteHttpURL:
        return (APP_URL / "index.php").with_query(
            shared_name=file.share_code,
            file_id=file.typed_id,
            rm="box_download_shared_file",
        )


class Node(TypedDict):
    name: str
    type: ReadOnly[Literal["file", "folder"]]
    id: int
    typed_id: str
    date: int
    parent_id: int


@dataclasses.dataclass(slots=True, frozen=True)
class File:
    id: int
    name: str
    typed_id: str
    date: int
    share_code: str

    @classmethod
    def from_node(cls, node: Node, share_code: str) -> Self:
        assert node["type"] == "file"
        return deserialize(cls, node, share_code=share_code)

    @property
    def url(self) -> AbsoluteHttpURL:
        return APP_URL / "s" / self.share_code / "file" / str(self.id)


@dataclasses.dataclass(slots=True, frozen=True)
class FileSystem:
    id: int
    name: str
    share_code: str
    nodes: dict[PurePosixPath, Node]


def _normalize_node(node: dict[str, Any]) -> Node:
    return {
        "name": node["name"],
        "type": node["type"],
        "id": node["id"],
        "typed_id": node["typedID"],
        "date": node.get("contentUpdated") or node["date"],
        "parent_id": node["parentFolderID"],
    }


def _build_file_system(nodes_map: Mapping[int, Node], root_id: int) -> dict[PurePosixPath, Node]:
    path_mapping: dict[PurePosixPath, Node] = {}
    parents_mapping: dict[int, list[Node]] = defaultdict(list)

    for node in nodes_map.values():
        parents_mapping[node["parent_id"]].append(node)

    def build_tree(parent_id: int, current_path: PurePosixPath) -> None:
        for node in parents_mapping.get(parent_id, []):
            item_path = current_path / node["name"]
            path_mapping[item_path] = node

            if node["type"] == "folder":
                build_tree(node["id"], item_path)

    path = PurePosixPath("/")
    path_mapping[path] = nodes_map[root_id]
    build_tree(root_id, path)
    return dict(sorted(path_mapping.items()))


def _parse_share(data: str) -> File | FileSystem:
    share: dict[str, Any] = json.loads(data)

    share_meta: dict[str, Any] = share["/app-api/enduserapp/shared-item"]
    share_code: str = share_meta["sharedName"]
    share_type: str = share_meta["type"]

    match share_type:
        case "file":
            file = next(f for key, f in share.items() if key.startswith("/app-api/enduserapp/item/f_"))
            node = _normalize_node(file["items"][0])
            return File.from_node(node, share_code)

        case "folder":
            folder = share["/app-api/enduserapp/shared-folder"]
            root_id = folder["currentFolderID"]
            nodes = {node["id"]: node for node in map(_normalize_node, folder["items"])}
            return FileSystem(
                id=root_id,
                name=folder["currentFolderName"],
                share_code=share_code,
                nodes=_build_file_system(nodes, root_id),
            )

        case _:
            raise ScrapeError(422, f"Unsupported {share_type = }")
