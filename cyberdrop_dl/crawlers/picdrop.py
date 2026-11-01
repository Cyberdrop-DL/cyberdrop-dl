from __future__ import annotations

import asyncio
import dataclasses
import json
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

from typing_extensions import AsyncGenerator

from cyberdrop_dl import aio
from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import extr_text
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.urls import remove_query_params

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class PicDropCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Gallery": "/<user>/<gallery_id>",
        "File": "/<user>/<gallery_id>?file=<file_key>",
    }
    DOMAIN: ClassVar[str] = "picdrop"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.picdrop.com")

    @staticmethod
    @override
    def __db_path__(url: AbsoluteHttpURL, /) -> str:
        return remove_query_params(url, keep=("file",)).path_qs

    def __post_init__(self) -> None:
        self.api: PicDropAPI = PicDropAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [user, gallery_id]:
                await self.gallery(scrape_item, user, gallery_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def gallery(self, scrape_item: ScrapeItem, user: str, gid: str) -> None:
        gallery = await self.api.gallery(user, gid)
        scrape_item.setup_as_album(self.create_title(gallery.name, gallery.path), album_id=gallery.path)
        downloaded = await self.get_completed_by_album(gallery.path)

        if file_key := scrape_item.url.query.get("file"):
            files = aio.to_async_iterable([await self.api.file(gallery.path, file_key)])
        else:
            files = self.api.files(gallery.path)

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            async for file in files:
                url = scrape_item.url.with_query(file=file.key)
                if url in downloaded:
                    continue

                new_item = scrape_item.create_child(scrape_item.url.with_query(file=file.key))
                tg.create_task(self._file(new_item, file, gallery.path))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def _file(self, scrape_item: ScrapeItem, file: File, path: str) -> None:
        filename, ext = self.get_filename_and_ext(file.name)
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            file.name,
            ext,
            custom_filename=filename,
            debrid_link=lambda: self.api.download(path, file.key),
            thumbnail=file.thumb,
            uploaded_at=int(self.parse_iso_date(file.uploadedAt)),
            metadata=file,
        )


@dataclasses.dataclass(slots=True, frozen=True)
class File:
    key: str
    name: str
    size: int
    type: str
    status: str
    order: int
    thumb: str | None
    uploadedAt: str  # noqa: N815

    @classmethod
    def parse(cls, file: dict[str, Any]) -> Self:
        if thumbs := file.get("thumbnails"):
            _, thumb = max(((t["width"], t["height"]), t["url"]) for t in thumbs)
        else:
            thumb = None

        return deserialize(cls, file, thumb=thumb)


@dataclasses.dataclass(slots=True, frozen=True)
class Gallery:
    key: str
    name: str
    user: str
    id: str
    numFiles: int  # noqa: N815
    path: str


@HTTPConfig(rate_limit=(10, 1))
class PicDropAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.picdrop.com/api")

    def __post_init__(self) -> None:
        self._csrf_token: str = ""
        self._token_lock: asyncio.Lock = asyncio.Lock()

    async def gallery(self, user: str, gid: str) -> Gallery:
        if not self._csrf_token:
            async with self._token_lock:
                if not self._csrf_token:
                    html = await self.request_text(self.PRIMARY_URL / user / gid)
                    data = json.loads(extr_text(html, '"xsrf":', "}") + "}")
                    self._csrf_token = data["value"]

        path = f"{user}:{gid}"
        resp = await self.request_json(self.ENTRYPOINT / "content" / path)
        return deserialize(Gallery, resp, id=gid, path=path, user=user)

    async def files(self, path: str) -> AsyncGenerator[File]:
        url = (self.ENTRYPOINT / "content" / path / "files").with_query(limit=500)
        while True:
            resp = await self.request_json(url)
            for file in resp["files"]:
                yield File.parse(file)

            if not resp.get("hasMore"):
                break

            url = url.update_query(offset=resp["lastSortKey"])

    async def file(self, path: str, key: str) -> File:
        url = self.ENTRYPOINT / "content" / path / "files" / key
        resp = await self.request_json(url)
        return File.parse(resp)

    async def download(self, path: str, key: str) -> AbsoluteHttpURL:
        assert self._csrf_token
        resp = await self.request_json(
            self.ENTRYPOINT / "download" / path,
            "PUT",
            json={
                "file": {
                    "key": key,
                    "type": "attachment",
                },
            },
            headers={
                "x-xsrf-key": self._csrf_token,
                "Origin": str(self.PRIMARY_URL),
                "Host": self.PRIMARY_URL.host,
            },
        )
        return self.parse_url(resp["downloadUrl"])
