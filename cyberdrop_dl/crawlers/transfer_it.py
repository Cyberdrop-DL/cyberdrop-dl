from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, cast

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.downloader import mega_nz as mega
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from pathlib import Path

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem
    from cyberdrop_dl.managers.manager import Manager


@dataclasses.dataclass(slots=True, frozen=True)
class File:
    name: str
    id: str
    transfer_id: str
    timestamp: int | None
    password: str | None = None


class TransferItAPI(mega.MegaApi):
    def __init__(self, manager: Manager) -> None:
        super().__init__(manager)
        self.entrypoint = "https://bt7.api.mega.co.nz/cs"
        self._url = AbsoluteHttpURL(self.entrypoint)
        self.shared_keys: mega.SharedkeysDict = {}
        self._default_params = {"v": 3, "domain": "transferit", "lang": "en", "bc": 1}

    async def request(
        self,
        data_input: list[dict[str, Any]] | dict[str, Any],
        add_params: dict[str, Any] | None = None,
    ) -> Any:
        add_params = self._default_params | (add_params or {})
        return await super().request(data_input, add_params)

    async def get_transfer_nodes(self, transfer_id: str) -> dict[str, mega.FileOrFolder]:
        folder: mega.Folder = await self.request(
            {"a": "f", "c": 1, "r": 1, "xnc": 1},
            {"x": transfer_id},
        )
        nodes = await self._process_nodes(folder["f"])
        return cast("dict[str, mega.FileOrFolder]", nodes)

    def _process_node(self, node: mega.Node) -> mega.Node:  # pyright: ignore[reportIncompatibleMethodOverride]
        node_type = node["t"]
        if node_type == mega.NodeType.FILE or node_type == mega.NodeType.FOLDER:
            attributes_bytes = mega.base64_url_decode(node["a"])
            full_key = mega.base64_to_a32(node["k"])
            crypto = mega.get_decrypt_data(node_type, full_key)
            attributes = mega.decrypt_attr(attributes_bytes, crypto.k)
            node["attributes"] = cast("mega.Attributes", attributes)  # pyright: ignore[reportInvalidCast]
        return node

    def get_download_link(self, file: File, *, direct: bool = True) -> AbsoluteHttpURL:
        if not direct:
            raise NotImplementedError
        url = (self._url / "g").with_query(x=file.transfer_id, n=file.id, fn=file.name)
        if file.password:
            return url.update_query(pw=file.password)
        return url


class TransferItCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Transfer": "/t/<transfer_id>"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://transfer.it")
    DOMAIN: ClassVar[str] = "transfer.it"

    def __post_init__(self) -> None:
        self.api = TransferItAPI(self.manager)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["t", transfer_id]:
                return await self.transfer(scrape_item, transfer_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def transfer(self, scrape_item: ScrapeItem, transfer_id: str) -> None:
        # TODO: handle expired links and password protected links
        nodes = await self.api.get_transfer_nodes(transfer_id)
        root_id = next(iter(nodes))
        root_name = nodes[root_id]["attributes"]["n"]
        filesystem = await self.api.build_file_system(nodes, [root_id])
        title = self.create_title(root_name, transfer_id)
        scrape_item.setup_as_album(title, album_id=transfer_id)
        self._process_filesystem(scrape_item, filesystem, transfer_id)

    def _process_filesystem(self, scrape_item: ScrapeItem, filesystem: dict[Path, mega.Node], transfer_id: str) -> None:
        password = scrape_item.url.query.get("pw") or scrape_item.password

        def filter_files():
            for path, node in filesystem.items():
                if node["t"] != mega.NodeType.FILE:
                    continue

                attrs = node["attributes"]
                timestamp = node.get("ts") or attrs.get("t")
                file = File(
                    name=attrs["n"],
                    id=node["h"],
                    transfer_id=transfer_id,
                    password=password,
                    timestamp=timestamp if isinstance(timestamp, int) else None,
                )
                yield path, file

        for path, file in filter_files():
            canonical_url = scrape_item.url.with_fragment(file.id)
            new_scrape_item = scrape_item.create_child(canonical_url)
            for part in path.parent.parts[1:]:
                new_scrape_item.add_to_parent_title(part)

            self.create_task(self._file(new_scrape_item, file))
            scrape_item.add_children()

    @error_handling_wrapper
    async def _file(self, scrape_item: ScrapeItem, file: File) -> None:
        link = self.api.get_download_link(file)
        filename, ext = self.get_filename_and_ext(file.name)
        scrape_item.possible_datetime = file.timestamp
        await self.handle_file(link, scrape_item, file.name, ext, custom_filename=filename)
