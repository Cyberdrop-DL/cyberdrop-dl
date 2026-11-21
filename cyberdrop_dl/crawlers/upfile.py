from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
from collections import deque
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Unpack, override

from Crypto.Cipher import AES
from Crypto.Util import Counter

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.downloader.http import Downloader
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.mediaprops import Codecs
from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.m3u8 import M3U8, Rendition

if TYPE_CHECKING:
    from cyberdrop_dl.constants import HttpMethod
    from cyberdrop_dl.network.request import RequestParams
    from cyberdrop_dl.url_objects import ScrapeItem

_PT = ContextVar[str]("_PT")
_MEDIA_ID = ContextVar[str]("_MEDIA_ID")
_KEY = ContextVar[bytes]("_KEY")


class UpFileDownloader(Downloader):
    @override
    async def _download_file(self, media_item: MediaItem) -> bool | None:
        downloaded = await super()._download_file(media_item)
        if downloaded:
            key = _KEY.get()
            media_key = _build_media_key(media_item.real_url, _MEDIA_ID.get())
            UpFileCrawler.get_logger().debug(
                "Decrypting content for %s :\n%s",
                media_item.real_url,
                {"key": key, "media_key": media_key},
            )
            content = await aio.read_bytes(media_item.path)
            await aio.write_bytes(media_item.path, await _decrypt(media_key, content, key))
        return downloaded


def _build_media_key(url: AbsoluteHttpURL, media_id: str) -> str:
    match url.parts[-2:]:
        case [_, "vinit"]:
            media_key = f"init:{media_id}"
        case [_, "img"]:
            media_key = f"img:{media_id}"
        case [_, "thumb"]:
            media_key = f"thumb:{media_id}"
        case ["seg", idx]:
            media_key = f"seg:{media_id}:{idx}"
        case _:
            raise ValueError(f"Unknown media URL {url}")

    return media_key


@aio.to_thread
def _decrypt(media_key: str, content: bytes, key: bytes) -> bytes:
    hash_bytes = hashlib.sha256(media_key.encode("utf-8")).digest()
    iv = hash_bytes[:8].ljust(16, b"\x00")
    ctr = Counter.new(64, prefix=iv[:8], initial_value=int.from_bytes(iv[8:], "big"))
    return AES.new(key, AES.MODE_CTR, counter=ctr).decrypt(content)


class UpFileCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Share": "/public/<path>...",
        "Share subfolder": "/public/<path>...?f=<subfolder_id>",
    }
    DOMAIN: ClassVar[str] = "upfile.top"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://upfile.top")

    def __post_init__(self) -> None:
        self.downloader: UpFileDownloader = self._build_downloader(UpFileDownloader)  # pyright: ignore[reportIncompatibleVariableOverride]
        self.api: UpFileAPI = UpFileAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["public", _, *_]:
                await self.share(
                    scrape_item,
                    path=scrape_item.url.path.removeprefix("/public/"),
                    subfolder=scrape_item.url.query.get("f"),
                )
            case _:
                raise ValueError

    @error_handling_wrapper
    async def share(self, scrape_item: ScrapeItem, path: str, subfolder: str | None = None) -> None:
        await self.api.boot(path)
        folder = await self.api.list(path, subfolder)
        root = folder.breadcrumb[0]
        scrape_item.setup_as_album(self.create_title(root.name, root.id), album_id=root.id)
        await self._walk_nodes(scrape_item, folder, path)

    async def _walk_nodes(self, scrape_item: ScrapeItem, folder: Folder, path: str) -> None:
        subfolders: deque[str] = deque()
        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            while True:
                nodes = folder.items
                leafs = tuple(node.name for node in folder.breadcrumb[1:])
                for node in nodes:
                    if node["type"] == "folder":
                        subfolders.append(node["id"])
                        continue

                    if node["type"] != "file":
                        self.log.warning("Unknown node type: %s", node)
                        continue

                    file = File.parse(node, path=path)
                    url = scrape_item.url / "m" / file.id
                    new_item = scrape_item.create_child(url)
                    new_item.append_folders(*leafs)
                    tg.create_task(self._file(new_item, file))
                    scrape_item.add_children()
                    await sleep()

                if not subfolders:
                    return

                folder = await self.api.list(path, subfolder=subfolders.popleft())

    @error_handling_wrapper
    async def _file(self, scrape_item: ScrapeItem, file: File) -> None:
        media_url = self.api.ENTRYPOINT / file.path / "m" / file.id
        if await self.check_complete(media_url):
            return

        _MEDIA_ID.set(file.id)
        filename, ext = self.get_filename_and_ext(file.name)
        debrid_url = m3u8 = meta = None
        match file.kind:
            case "video":
                meta = await self.api.video(file.path, file.id)
                m3u8 = Rendition(_create_m3u8(media_url, len(meta.segments), meta.duration), None, None)
            case "image":
                debrid_url = media_url / "img"
            case _:
                raise ScrapeError(422, f"Unsupported file type: {file}")

        await self.handle_file(
            media_url,
            scrape_item,
            file.name,
            ext,
            custom_filename=filename,
            headers=self.api.headers,
            thumbnail=media_url / "thumb" if file.thumb else None,
            debrid_link=debrid_url,
            m3u8=m3u8,
            metadata=meta,
        )

    @override
    def _prepare_media_item(self, media_item: MediaItem) -> None:
        media_item.headers.update(self.api.headers)

    @override
    async def sniff_ext(
        self, url: AbsoluteHttpURL, /, method: HttpMethod | None = None, **kwargs: Unpack[RequestParams]
    ) -> str:
        if url.name == "thumb":
            return ".jpg"
        return await super().sniff_ext(url, method, **kwargs)


@dataclasses.dataclass(slots=True, frozen=True)
class Node:
    id: str
    name: str
    parse = classmethod(deserialize)


@dataclasses.dataclass(slots=True, frozen=True)
class File(Node):
    path: str
    type: Literal["file"]
    thumb: bool
    status: str
    kind: str


@dataclasses.dataclass(slots=True, frozen=True)
class Folder(Node):
    breadcrumb: tuple[Node, ...]
    items: list[dict[str, Any]]
    type: Literal["folder"] = "folder"


@dataclasses.dataclass(slots=True, frozen=True)
class VideoMeta:
    segments: list[int]
    codecs: Codecs
    duration: int
    width: int
    height: int


class UpFileAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://upfile.top/api/s")

    @property
    def headers(self) -> dict[str, str]:
        return {"x-pt": _PT.get(), "cache": "no-store"}

    async def boot(self, path: str) -> None:
        html = await self.request_text(self.PRIMARY_URL / "public" / path)
        _PT.set(await _extract_boot_token(html))
        init = await self.request_json(self.ENTRYPOINT / path / "init", "POST", json={}, headers=self.headers)
        _KEY.set(base64.b64decode(init["key"]))

    async def list(self, path: str, subfolder: str | None = None) -> Folder:
        url = self.ENTRYPOINT / path / "list"
        if subfolder:
            url = url.update_query(folder=subfolder)
        data = await self.request_json(url, headers=self.headers)
        return Folder.parse(
            data["folder"],
            items=data["items"],
            breadcrumb=tuple(map(Node.parse, data["breadcrumb"])),
        )

    async def video(self, path: str, media_id: str) -> VideoMeta:
        play = self.ENTRYPOINT / path / "play"
        data = await self.request_json(play, "POST", json={"id": media_id}, headers=self.headers)
        return deserialize(VideoMeta, meta := data["meta"], codecs=Codecs.parse(meta["codecs"]))


@aio.to_thread
def _extract_boot_token(html: str) -> str:
    soup = css.soup(html, parse_only="script")
    boot = json.loads(css.select_text(soup, "#boot"))
    return boot["pt"]


def _create_m3u8(url: AbsoluteHttpURL, segments: int, duration: int) -> M3U8:
    target_duration = int(duration) + (1 if duration % 1 > 0 else 0)

    def lines():
        yield "#EXTM3U"
        yield f"#EXT-X-TARGETDURATION:{target_duration}"
        yield "#EXT-X-VERSION:3"
        yield "#EXT-X-MEDIA-SEQUENCE:0"
        yield "#EXT-X-PLAYLIST-TYPE:VOD"
        yield f"#EXTINF:{duration:.6f},"
        yield "vinit"

        for idx in range(segments):
            yield f"#EXTINF:{duration:.6f},"
            yield f"seg/{idx}"

        yield "#EXT-X-ENDLIST"

    content = "\n".join(lines())
    return M3U8(content, base_uri=url, media_type="video", source=url)
