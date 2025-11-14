from __future__ import annotations

import dataclasses
from typing import Any, ClassVar, Literal

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths, auto_task_id
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.exceptions import DownloadError, PasswordProtectedError, ScrapeError
from cyberdrop_dl.utils.utilities import error_handling_wrapper, type_adapter

_APP_URL = AbsoluteHttpURL("https://app.koofr.net")
_APP_LINKS = _APP_URL / "api/v2/public/links"
_PRIMARY_URL = AbsoluteHttpURL("https://koofr.eu")
_SHORT_LINK_CDN = AbsoluteHttpURL("https://k00.fr")


@dataclasses.dataclass(slots=True)
class Node:
    name: str
    type: Literal["file", "dir"]
    modified: int
    hash: str  # md5


@dataclasses.dataclass(slots=True)
class Folder:
    name: str
    file: Node
    root_id: str = ""
    password: str = ""
    children: list[Node] = dataclasses.field(default_factory=list)


_parse_folder = type_adapter(Folder)
_parse_node = type_adapter(Node)


class KooFrCrawler(Crawler):
    SUPPORTED_DOMAIN = "koofr.net", "koofr.eu", _SHORT_LINK_CDN.host
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File / Folder": (
            "/links/<content_id>",
            f"{_SHORT_LINK_CDN}/<short_id>",
        ),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = _PRIMARY_URL
    DOMAIN: ClassVar[str] = "koofr"

    def __post_init__(self) -> None:
        self.api = KooFrAPI(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if scrape_item.url.host == _SHORT_LINK_CDN.host:
            return await self.follow_redirect(scrape_item)

        match scrape_item.url.parts[1:]:
            case ["links", content_id]:
                return await self.content(scrape_item, content_id)
            case _:
                raise ValueError

    async def _get_redirect_url(self, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        async with self.request(url) as resp:
            if password := url.query.get("password"):
                return resp.url.update_query(password=password)
            return resp.url

    @error_handling_wrapper
    async def content(self, scrape_item: ScrapeItem, content_id: str) -> None:
        path = scrape_item.url.query.get("path") or "/"
        folder = await self.api.get_folder(content_id, path, scrape_item.password)
        if not folder.file.type == "file":
            return await self._file(scrape_item, folder.file)

        title = self.create_title(folder.file.name, content_id)
        scrape_item.setup_as_album(title, album_id=content_id)
        await self._walk_folder(scrape_item, folder, path)

    @error_handling_wrapper
    async def _walk_folder(self, scrape_item: ScrapeItem, folder: Folder, path: str):
        children = await self.api.get_children(folder, path)
        for node in children:
            if node.type == "file":
                self.create_task(self._file(scrape_item, node))
                continue

            else:
                new_path = f"{path}/{node.name}"
                new_scrape_item = scrape_item.create_child(scrape_item.url.update_query(path=path))
                new_scrape_item.add_to_parent_title(node.name)
                self.create_task(self._walk_folder_task(new_scrape_item, folder, new_path))

            scrape_item.add_children()

    _walk_folder_task = auto_task_id(_walk_folder)

    @error_handling_wrapper
    async def _file(self, scrape_item: ScrapeItem, file: Node) -> None:
        content_id = scrape_item.url.name
        link = (_APP_URL / "content/links" / content_id / "files/get" / file.name).with_query(scrape_item.url.query)
        if await self.check_complete_by_hash(link, "md5", file.hash):
            return

        filename, ext = self.get_filename_and_ext(file.name)
        scrape_item.possible_datetime = file.modified
        await self.handle_file(link, scrape_item, file.name, ext, custom_filename=filename)


class KooFrAPI:
    def __init__(self, crawler: KooFrCrawler) -> None:
        self._crawler = crawler

    async def get_folder(self, content_id: str, path: str, password: str | None) -> Folder:
        password = password or ""
        api_url = (_APP_LINKS / content_id).with_query(path=path, password=password)
        try:
            resp: dict[str, Any] = await self._crawler.request_json(api_url)
        except DownloadError as e:
            if e.status == 401:
                msg = "Incorrect password" if password else None
                raise PasswordProtectedError(msg) from e
            raise

        if not resp.get("isOnline"):
            raise ScrapeError(404)

        folder = _parse_folder(resp)
        folder.password = password
        folder.root_id = content_id
        return folder

    async def get_children(self, folder: Folder, path: str) -> list[Node]:
        api_url = (_APP_LINKS / folder.root_id / "bundle").with_query(path=path, password=folder.password)
        nodes = (await self._crawler.request_json(api_url))["files"]
        return [_parse_node(node) for node in nodes]
