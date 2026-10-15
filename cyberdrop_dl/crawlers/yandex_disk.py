from __future__ import annotations

import contextlib
import dataclasses
import json
from collections import deque
from contextvars import ContextVar
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, cast

from cyberdrop_dl import aio
from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.exceptions import DDOSGuardError, DownloadError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.clients.response import AbstractResponse
    from cyberdrop_dl.url_objects import ScrapeItem


POSIX_ROOT = PurePosixPath("/")
SHARE_ID = ContextVar[str]("SHARE_ID")


class _WrongSkError(ScrapeError):
    def __init__(self, new_sk: str) -> None:
        super().__init__(403, "Yandex rejected the session token (sk)")
        self.new_sk: str = new_sk


def _raise_for_wrong_sk(resp: Any, _: AbstractResponse[Any] | None = None) -> None:
    # Yandex answers the download API with a 400 when the sk does not match the session cookie
    if not isinstance(resp, dict):
        return

    resp = cast("dict[str, Any]", resp)
    new_sk: str | None = resp.get("newSk")
    if resp.get("wrongSk") and new_sk:
        raise _WrongSkError(new_sk)


@HTTPConfig(json_check=_raise_for_wrong_sk, headers={"Accept-Language": "en-US,en;q=0.5"})
class YandexDiskCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "disk.yandex", "yadi.sk", "disk.360.yandex"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Share": "/d/<share_id>",
        "File": (
            "/d/<share_id>/<sub_path>",
            "/i/<file_id>",
        ),
    }

    DOMAIN: ClassVar[str] = "disk.yandex"
    FOLDER_DOMAIN: ClassVar[str] = "YandexDisk"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://disk.yandex.com")

    def __post_init__(self) -> None:
        self.api: YandexDiskAPI = YandexDiskAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["d", share_id, *rest]:
                await self.share(scrape_item, share_id, subpath=POSIX_ROOT.joinpath(*rest))
            case ["i", _]:
                await self.file(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        share = await self.api.share(scrape_item.url)
        file = YandexFile.from_share(share)
        await self._file(scrape_item, file)

    @error_handling_wrapper
    async def share(self, scrape_item: ScrapeItem, share_id: str, subpath: PurePosixPath | None = None) -> None:
        canonical_url = self.PRIMARY_URL / "d" / share_id
        scrape_item.url = canonical_url
        SHARE_ID.set(share_id)

        share = await self.api.share(scrape_item.url)
        if len(share.resources) == 1 and not share.currentResourceId:
            file = YandexFile.from_share(share)
            await self._file(scrape_item, file)
            return

        folder = YandexFolder.from_share(share)
        scrape_item.setup_as_album(self.create_title(folder.name, folder.id), album_id=folder.id)
        await self._walk_nodes(scrape_item, folder, subpath)

    async def _walk_nodes(
        self,
        scrape_item: ScrapeItem,
        folder: YandexFolder,
        subpath: PurePosixPath | None,
    ) -> None:
        subfolders: deque[tuple[PurePosixPath, str, str]] = deque()
        current_path = POSIX_ROOT
        subpath = subpath or POSIX_ROOT
        nodes = [folder.resources[child_id] for child_id in folder.children_ids]

        while True:
            for node in nodes:
                if node["type"] == "dir":
                    inner_path = current_path / node["name"]
                    if subpath.is_relative_to(inner_path) or inner_path.is_relative_to(subpath):
                        subfolders.append((current_path / node["name"], node["id"], node["path"]))
                    continue

                if node["type"] != "file":
                    self.log.warning("Unknown node type: %s", node)
                    continue

                file = YandexFile.from_json(node, sk=folder.sk)
                if not (current_path / file.name).is_relative_to(subpath):
                    continue

                new_item = scrape_item.create_child(self.PRIMARY_URL / file.web_path)
                new_item.append_folders(*current_path.parts[1:])
                self.create_eager_task(self._file(new_item, file))
                scrape_item.add_children()

            if not subfolders:
                return

            current_path, node_id, node_path = subfolders.popleft()
            nodes = await self.api.list_folder(node_id, node_path, sk=folder.sk)

    @error_handling_wrapper
    async def _file(self, scrape_item: ScrapeItem, file: YandexFile) -> None:
        url = self.origin / file.web_path
        if await self.check_complete(url):
            return

        scrape_item.uploaded_at = file.modified
        src = await self.api.download(file)
        name = src.query.get("filename") or file.name
        filename, ext = self.get_filename_and_ext(name, mime_type=file.mimetype)
        await self.handle_file(url, scrape_item, name, ext, debrid_link=src, custom_filename=filename)


class YandexDiskAPI(API):
    def __post_init__(self) -> None:
        self._host_locks: aio.WeakAsyncLocks[str] = aio.WeakAsyncLocks()
        self._hosts_with_session: set[str] = set()

    @contextlib.contextmanager
    def _request_context(self) -> Generator[None]:
        try:
            yield
        except DownloadError as e:
            if e.status in {400, 403}:
                raise DDOSGuardError from None
            raise

    async def share(self, url: AbsoluteHttpURL) -> Share:
        html = await self._request_html(url)
        data = json.loads(css.select_text(await css.asoup(html, parse_only="script"), "script#store-prefetch"))
        return deserialize(Share, data, sk=data["environment"]["sk"], path=url.path.removeprefix("/"))

    async def _request_html(self, url: AbsoluteHttpURL) -> str:
        # Yandex ties the sk embedded in a page to the session cookie it sets with that page.
        # If the first pages of a host are requested concurrently, each one starts a new session and
        # overwrites the previous cookie, so only the sk of the last page stays valid.
        # Let the first request of each host set the session cookie before any other page is requested
        with self._request_context():
            if url.host not in self._hosts_with_session:
                async with self._host_locks[url.host]:
                    if url.host not in self._hosts_with_session:
                        html = await self.request_text(url)
                        self._hosts_with_session.add(url.host)
                        return html

            return await self.request_text(url)

    async def _download(self, file: YandexFile) -> dict[str, Any]:
        api_url = self.origin / "public/api/download-url"
        referer = self.origin / file.web_path
        return await self.post_json(
            api_url,
            headers={
                "Referer": str(referer),
                "X-Retpath-Y": str(referer),
            },
            params={"hash": file.path, "inline": False, "sk": file.sk},
        )

    async def post_json(
        self, api_url: AbsoluteHttpURL, params: dict[str, Any], headers: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        with self._request_context():
            return await self.request_json(
                api_url,
                method="POST",
                headers={
                    "Content-Type": "text/plain",
                    "X-Requested-With": "XMLHttpRequest",
                    "Origin": str(self.origin),
                    **(headers or {}),
                },
                data=json.dumps(params, separators=(",", ":")),
            )

    async def download(self, file: YandexFile) -> AbsoluteHttpURL:
        # The session can still change mid-run. Yandex then answers with a 400 and the sk that is valid now
        for retry in (True, False):
            try:
                resp = await self._download(file)
            except _WrongSkError as e:
                if not retry:
                    raise
                self.log.debug("Yandex rejected the sk for %s, retrying with the one it sent back", file.path)
                file = file.with_sk(e.new_sk)
            else:
                if resp.get("error"):
                    raise ScrapeError(422, message=str(resp)[:50])
                return self.parse_url(resp["data"]["url"])

        raise RuntimeError

    async def list_folder(self, node_id: str, path: str, sk: str) -> list[dict[str, Any]]:
        url = self.origin / "public/api/fetch-list"
        resp = await self.post_json(url, params={"hash": path, "offset": 0, "withSizes": "true", "sk": sk})
        return [node for node in resp["resources"] if node.get("id") != node_id]


@dataclasses.dataclass(frozen=True, kw_only=True)
class Share:
    sk: str
    path: str
    resources: dict[str, dict[str, Any]]
    currentResourceId: str | None = None  # noqa: N815


@dataclasses.dataclass(frozen=True, kw_only=True)
class YandexItem:
    id: str
    sk: str
    path: str
    name: str
    modified: int

    def with_sk(self, new_sk: str) -> Self:
        return dataclasses.replace(self, sk=new_sk)


@dataclasses.dataclass(frozen=True, kw_only=True)
class YandexFolder(YandexItem):
    type: Literal["dir"]
    resources: dict[str, dict[str, Any]]
    children_ids: list[str]

    @classmethod
    def from_share(cls, share: Share) -> Self:
        assert share.currentResourceId
        details = share.resources.pop(share.currentResourceId)
        return deserialize(
            cls,
            details,
            resources=share.resources,
            sk=share.sk,
            children_ids=details["children"],
        )


@dataclasses.dataclass(frozen=True, kw_only=True)
class YandexFile(YandexItem):
    type: Literal["file"]
    mimetype: str
    web_path: str = ""

    def __post_init__(self) -> None:
        if not self.web_path:
            _hash, _, path = self.path.partition(":/")
            assert path
            object.__setattr__(self, "web_path", f"d/{SHARE_ID.get()}/{path}")

    @classmethod
    def from_json(cls, details: dict[str, Any], sk: str) -> Self:
        return deserialize(cls, details, sk=sk, mimetype=details["meta"]["mimetype"])

    @classmethod
    def from_share(cls, share: Share) -> Self:
        assert len(share.resources) == 1
        details = next(iter(share.resources.values()))
        details["web_path"] = share.path
        return cls.from_json(details, sk=share.sk)
