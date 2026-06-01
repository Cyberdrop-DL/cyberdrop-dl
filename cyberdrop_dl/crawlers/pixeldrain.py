"""https://pixeldrain.com/api"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, Literal, final

from typing_extensions import override

from cyberdrop_dl.crawlers.crawler import API, Crawler, RateLimit, SupportedDomains, SupportedPaths, auto_task_id
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import basic_auth, error_handling_wrapper, type_adapter

if TYPE_CHECKING:
    from cyberdrop_dl.clients.response import AbstractResponse
    from cyberdrop_dl.url_objects import ScrapeItem


_PRIMARY_URL = AbsoluteHttpURL("https://pixeldrain.com")


@final
@dataclasses.dataclass(slots=True)
class File:
    id: str
    name: str
    date_upload: str
    mime_type: str
    hash_sha256: str


@dataclasses.dataclass(slots=True)
class Folder:
    id: str
    title: str
    files: list[File]


@final
@dataclasses.dataclass(slots=True)
class Node:
    type: Literal["file", "dir"]
    path: str
    name: str
    modified: str
    sha256_sum: str
    id: str | None = None
    file_type: str | None = None

    # Properties so we can process a Node as a normal File
    @property
    def mime_type(self) -> str:
        return self.file_type or ""

    @property
    def date_upload(self) -> str:
        return self.modified

    @property
    def hash_sha256(self) -> str:
        return self.sha256_sum


@dataclasses.dataclass(slots=True)
class FileSystem:
    children: list[Node]
    base_index: int
    path: list[Node]


class PixelDrainProxyCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"File": "/<file_id>"}
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "pd.cybar.xyz", "pd.1drv.eu.org"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pd.1drv.eu.org")
    DOMAIN: ClassVar[str] = "pixeldrain-proxy"

    @override
    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["u", _]:
                return self.handle_external_links(scrape_item)
            case _:
                raise ValueError

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url).with_host("pixeldrain.com")
        match url.parts[1:]:
            case [file_id]:
                return url.origin() / "u" / file_id
            case _:
                return url


class PixelDrainCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = (
        "pixeldrain.com",
        "pixeldrain.net",
        "pixeldra.in",
        "pixeldrain.nl",
        "pixeldrain.biz",
        "pixeldrain.tech",
        "pixeldrain.dev",
    )
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File": (
            "/u/<file_id>",
            "/l/<list_id>#item=<file_index>",
            "/api/file/<file_id>",
        ),
        "Folder": (
            "/l/<list_id>",
            "/api/list/<list_id>",
        ),
        "Filesystem": (
            "/d/<id>",
            "/api/filesystem/<path>...",
        ),
        "**NOTE**": "text files will not be downloaded but their content will be parsed for URLs",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = _PRIMARY_URL
    DOMAIN: ClassVar[str] = "pixeldrain"
    FOLDER_DOMAIN: ClassVar[str] = "PixelDrain"
    _RATE_LIMIT: ClassVar[RateLimit] = 10, 1
    _DOWNLOAD_SLOTS: ClassVar[int | None] = 2

    def __post_init__(self) -> None:
        self.api: PixelDrainAPI = PixelDrainAPI(self)
        if self.api.logged_in:
            self.downloader.download_slots = None

    @classmethod
    @override
    def __json_resp_check__(cls, json_resp: dict[str, Any], resp: AbstractResponse[Any]) -> None:
        if not json_resp["success"]:
            msg = f"{json_resp['message']} ({json_resp['value']})"
            raise ScrapeError(resp.status, msg)

    @override
    def _prepare_headers(self, scrape_item: ScrapeItem) -> dict[str, str]:
        return super()._prepare_headers(scrape_item) | self.api.headers

    @override
    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["u", file_id]:
                return await self.file(scrape_item, file_id)
            case ["l", folder_id]:
                return await self.folder(scrape_item, folder_id)
            case ["d", *path] if path:
                return await self.filesystem(scrape_item, "/".join(path))
            case _:
                raise ValueError

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["api", "file", file_id]:
                return url.origin() / "u" / file_id
            case ["api", "list", list_id]:
                return url.origin() / "l" / list_id
            case ["api", "filesystem", *rest] if rest:
                return (url.origin() / "d").joinpath(*rest)
            case _:
                return url

    @error_handling_wrapper
    async def folder(self, scrape_item: ScrapeItem, list_id: str) -> None:
        folder = await self.api.folder(list_id)
        title = self.create_title(folder.title, list_id)
        scrape_item.setup_as_album(title, album_id=list_id)

        try:
            files = _filter_files(folder.files, scrape_item.url.fragment)
        except (ValueError, IndexError):
            msg = f"Unable to parse item index in {scrape_item.url}. Falling back to downloading the entire folder"
            self.log.warning(msg)
            files = folder.files

        await self._files(scrape_item, files)

    async def _files(self, scrape_item: ScrapeItem, files: list[File]) -> None:
        assert scrape_item.album_id
        results = await self.get_album_results(scrape_item.album_id)
        for file in files:
            if self.check_album_results(_build_download_url(file), results):
                continue

            url = self.origin / "u" / file.id
            new_scrape_item = scrape_item.create_child(url)
            self.create_task(self._file_task(new_scrape_item, file))
            scrape_item.add_children()

    @error_handling_wrapper
    async def filesystem(self, scrape_item: ScrapeItem, path: str) -> None:
        # https://github.com/Fornaxian/pixeldrain_web/blob/8e5ecfc5ce44c0b2b4fafdf9e8201dfc98395e88/svelte/src/filesystem/FilesystemAPI.ts
        fs = await self.api.filesystem(path)
        base_node = fs.path[fs.base_index]
        root = fs.path[0]
        assert root.id
        title = self.create_title(root.name, root.id)
        scrape_item.setup_as_album(title, album_id=root.id)

        if base_node.type == "file":
            fs.children = [base_node]

        await self._filesystem(scrape_item, fs)

    async def _filesystem(self, scrape_item: ScrapeItem, fs: FileSystem) -> None:
        assert scrape_item.album_id
        results = await self.get_album_results(scrape_item.album_id)

        async def subfolder(new_item: ScrapeItem, path: str) -> None:
            with self.catch_errors(new_item):
                fs = await self.api.filesystem(path)
                scrape_item.add_children(0)
                walk_filesystem(fs)

        def walk_filesystem(fs: FileSystem) -> None:
            for node in fs.children:
                if node.name == ".search_index.gz":
                    continue

                url = self.origin / "d" / node.path.removeprefix("/")
                new_scrape_item = scrape_item.create_child(url)

                if node.type == "file":
                    if self.check_album_results(_build_download_url(node), results):
                        continue

                    subfolders = node.path.split("/")[2:-1]
                    new_scrape_item.append_folders(*subfolders)
                    self.create_task(self._file_task(new_scrape_item, node))

                elif node.type == "dir":
                    self.create_task(subfolder(new_scrape_item, node.path))

                else:
                    self.raise_exc(new_scrape_item, f"Unknown node type: {node.type}")

                scrape_item.add_children()

        walk_filesystem(fs)

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, file_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        file = await self.api.file(file_id)
        await self._file(scrape_item, file)

    async def _file(self, scrape_item: ScrapeItem, file: File | Node) -> None:
        if "text/plain" in file.mime_type:
            return await self.text(scrape_item, file)

        src = _build_download_url(file).with_host(self.origin.host)
        if await self.check_complete_by_hash(src, "sha256", file.hash_sha256):
            return None

        filename, ext = self.get_filename_and_ext(file.name, mime_type=file.mime_type)
        scrape_item.uploaded_at = self.parse_iso_date(file.date_upload)
        await self.handle_file(src, scrape_item, file.name, ext, custom_filename=filename)

    @error_handling_wrapper
    async def text(self, scrape_item: ScrapeItem, file: File | Node) -> None:
        assert file.id
        scrape_item.setup_as_album(self.create_title(file.name, file.id))
        text = await self.api.text(file.id)

        for line in text.splitlines():
            try:
                link = self.parse_url(line)
            except Exception:  # noqa: BLE001, S112
                continue
            new_item = scrape_item.create_child(link)
            self.handle_external_links(new_item)
            scrape_item.add_children()

    _file_task = auto_task_id(error_handling_wrapper(_file))


class PixelDrainAPI(API):
    def __post_init__(self) -> None:
        self.headers: dict[str, str] = {}
        if api_key := self.config.auth.pixeldrain.api_key:
            self.headers["Authorization"] = basic_auth("Cyberdrop-DL", api_key)

    @property
    def logged_in(self) -> bool:
        return bool(self.headers)

    async def file(self, file_id: str) -> File:
        api_url = self.origin / "api/file" / file_id / "info"
        resp = await self._request(api_url)
        return type_adapter(File).validate_json(resp)

    async def text(self, file_id: str) -> str:
        api_url = self.origin / "api/file" / file_id
        return await self._request(api_url)

    async def folder(self, list_id: str) -> Folder:
        api_url = self.origin / "api/list" / list_id
        resp = await self._request(api_url)
        return type_adapter(Folder).validate_json(resp)

    async def filesystem(self, path: str) -> FileSystem:
        api_url = (self.origin / "api/filesystem" / path.removeprefix("/")).with_query("stat")
        resp = await self._request(api_url)
        return type_adapter(FileSystem).validate_json(resp)

    async def _request(self, api_url: AbsoluteHttpURL) -> str:
        return await self.request_text(api_url, headers=self.headers)


def _filter_files(files: list[File], fragment: str) -> list[File]:
    if fragment.startswith(prefix := "item="):
        item_idx = int(fragment.removeprefix(prefix))
        return [files[item_idx]]
    return files


def _build_download_url(file: File | Node) -> AbsoluteHttpURL:
    if type(file) is File:
        return (_PRIMARY_URL / "api/file" / file.id).with_query("download")
    return (_PRIMARY_URL / "api/filesystem" / file.path.removeprefix("/")).with_query("attach")
