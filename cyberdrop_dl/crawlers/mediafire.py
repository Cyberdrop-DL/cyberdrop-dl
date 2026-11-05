"""https://www.mediafire.com/developers/core_api"""

from __future__ import annotations

import asyncio
import base64
import itertools
from collections import deque
from http import HTTPStatus
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, override

from cyberdrop_dl import aio
from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers import Registry
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths, URLConfig, auto_task_id
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import b64_pad, css, is_blob_or_svg
from cyberdrop_dl.utils.dataclass import deserialize, struct
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    import aiosqlite

    from cyberdrop_dl.url_objects import ScrapeItem


@struct
class Folder:
    name: str
    folderkey: str
    has_files: bool
    has_folders: bool

    @classmethod
    def from_dict(cls, info: dict[str, Any]) -> Self:
        return cls(
            name=info["name"],
            folderkey=info["folderkey"],
            has_files=bool(int(info["file_count"])),
            has_folders=bool(int(info["folder_count"])),
        )


@struct
class File:
    quickkey: str
    filename: str
    created_utc: str
    size: int
    hash: str
    mimetype: str

    @classmethod
    def from_dict(cls, info: dict[str, Any]) -> Self:
        return deserialize(cls, info, size=int(info["size"]))


_API_ERRORS_OVERRIDES: Mapping[int, int] = MappingProxyType(
    {
        110: HTTPStatus.GONE,
        105: HTTPStatus.GONE,
        293: HTTPStatus.UNAVAILABLE_FOR_LEGAL_REASONS,
    }
)


@URLConfig(allow_empty_path=True)
class MediaFireCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File": (
            "/file/<quick_key>/...",
            "/file_premium/<quick_key>/...",
            "?<quick_key>",
        ),
        "Folder": "/folder/<folder_key>/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.mediafire.com")
    DOMAIN: ClassVar[str] = "mediafire"

    @staticmethod
    def __db_path__(url: AbsoluteHttpURL) -> str:
        match url.parts[1:]:
            case ["file" | "file_premium", quick_key, *_]:
                return quick_key
            case _:
                raise ValueError(url)

    def __post_init__(self) -> None:
        self.api: MediaFireAPI = MediaFireAPI.from_crawler(self)

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        if (
            url.path == "/"
            and url.query_string
            and not ("&" in url.query_string or "=" in url.query_string)
            and (quick_key := url.query_string.partition("/")[0])
        ):
            return cls.PRIMARY_URL / "file" / quick_key
        return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["folder", folder_key, *_]:
                await self.folder(scrape_item, folder_key)
            case ["file" | "file_premium" as kind, quick_key, *_]:
                await self.file(scrape_item, kind, quick_key)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def folder(self, scrape_item: ScrapeItem, folder_key: str) -> None:
        folder = await self.api.folder_info(folder_key)
        title = self.create_title(folder.name, folder_key)
        scrape_item.setup_as_album(title, album_id=folder_key)

        is_empty = not (folder.has_files or folder.has_folders)
        if is_empty:
            # Make a request anyway to try to get a descriptive error from MediaFire
            async for _ in self.api.subfolders(folder_key):
                break
            raise ScrapeError(204, "Folder is empty")

        await self._walk_folder(scrape_item, folder)

    async def _walk_folder(self, scrape_item: ScrapeItem, folder: Folder):
        downloaded = await self.get_completed_by_album(folder.folderkey)
        path: tuple[str, ...] = ()
        subfolders: deque[tuple[tuple[str, ...], str]] = deque()

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            while True:
                if folder.has_files:
                    async for file in self.api.files(folder.folderkey):
                        url = self.PRIMARY_URL / "file" / file.quickkey
                        if url in downloaded:
                            continue

                        new_item = scrape_item.create_child(url)
                        new_item.append_folders(*path)
                        tg.create_task(self._file_task(new_item, file))
                        scrape_item.add_children()
                        await sleep()

                if folder.has_folders:
                    async for subfolder in self.api.subfolders(folder.folderkey):
                        if subfolder.has_files or subfolder.has_folders:
                            subfolders.append(((*path, subfolder.name), subfolder.folderkey))
                            await sleep()

                if not subfolders:
                    break

                path, subfolder_key = subfolders.popleft()
                folder = await self.api.folder_info(subfolder_key)

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, kind: str, quick_key: str) -> None:
        canonical_url = self.PRIMARY_URL / kind / quick_key
        if await self.check_complete(canonical_url):
            return

        file = await self.api.file_info(quick_key)
        scrape_item.url = canonical_url
        await self._file(scrape_item, file)

    async def _file(self, scrape_item: ScrapeItem, file: File) -> None:
        checksum = "sha256" if len(file.hash) == 64 else "md5"
        if await self.check_complete_by_hash(scrape_item.url, checksum, file.hash):
            return

        html = await self.request_text(scrape_item.url, impersonate=True)
        src = self.parse_url(await asyncio.to_thread(_extract_dl, html))
        scrape_item.uploaded_at = self.parse_iso_date(file.created_utc)
        filename, ext = self.get_filename_and_ext(file.filename, mime_type=file.mimetype)
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            file.filename,
            ext,
            custom_filename=filename,
            debrid_link=src,
        )

    @auto_task_id
    @error_handling_wrapper
    async def _file_task(self, scrape_item: ScrapeItem, file: File) -> None:
        if await self.check_complete(scrape_item.url):
            return

        await self._file(scrape_item, file)


def _json_check(json_resp: Any, _: Any = None) -> None:
    if type(json_resp) is not dict or "response" not in json_resp:
        return

    resp: dict[str, Any] = json_resp["response"]
    if resp["result"] != "Success":
        code: int = resp["error"]
        if http_code := _API_ERRORS_OVERRIDES.get(code):
            raise ScrapeError(http_code)

        ui_failure = f"MediaFire Error ({code})"
        raise ScrapeError(ui_failure, resp["message"])


@HTTPConfig(json_check=_json_check)
class MediaFireAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.mediafire.com/api/1.4")

    async def _request(self, path: str, **params: int | str) -> dict[str, Any]:
        assert params
        params["response_format"] = "json"
        resp = await self.request_json((self.ENTRYPOINT / path).with_query(params))
        _json_check(resp)
        return resp["response"]

    async def _folder_content(
        self, folder_key: str, content_type: Literal["files", "folders"]
    ) -> AsyncGenerator[list[dict[str, Any]]]:
        for chunk in itertools.count(1):
            resp = await self._request(
                "folder/get_content.php",
                folder_key=folder_key,
                content_type=content_type,
                chunk=chunk,
                chunk_size=1000,
                filter="public",
            )
            content = resp["folder_content"]
            yield content[content_type]
            if content["more_chunks"] != "yes":
                break

    async def subfolders(self, folder_key: str) -> AsyncGenerator[Folder]:
        async for folders in self._folder_content(folder_key, "folders"):
            for folder in folders:
                yield Folder.from_dict(folder)

    async def files(self, folder_key: str) -> AsyncGenerator[File]:
        async for files in self._folder_content(folder_key, "files"):
            for file in files:
                yield File.from_dict(file)

    async def folder_info(self, folder_key: str) -> Folder:
        resp: dict[str, Any] = await self._request("folder/get_info.php", folder_key=folder_key)
        return Folder.from_dict(resp["folder_info"])

    async def file_info(self, quick_key: str) -> File:
        resp: dict[str, Any] = await self._request("file/get_info.php", quick_key=quick_key)
        return File.from_dict(resp["file_info"])


def _extract_dl(html: str) -> str:
    soup = css.soup(html)
    download_button = soup.select_one("a#downloadButton")
    if not download_button:
        if "Something appears to be missing" in html:
            raise ScrapeError(410)
        raise ScrapeError(422)

    if encoded_url := css.attr_or_none(download_button, "data-scrambled-url"):
        return base64.b64decode(b64_pad(encoded_url)).decode()

    url = css.attr(download_button, "href")
    if is_blob_or_svg(url):
        raise ScrapeError(422, "Unable to extract download URL")
    return url


def fix_db_path(url_path: str, referer: str) -> str:
    try:
        ref_url = MediaFireCrawler.transform_url(MediaFireCrawler.parse_url(referer, trim=False))
        return MediaFireCrawler.__db_path__(ref_url)
    except ValueError:
        return url_path


@Registry.database.custom_fix_for(MediaFireCrawler)
async def fix_db_paths(db_conn: aiosqlite.Connection) -> None:
    fn_name = f"FIX_{MediaFireCrawler.DOMAIN.upper()}_DB_PATH"
    await db_conn.create_function(fn_name, 2, fix_db_path, deterministic=True)
    updates = f"UPDATE OR REPLACE media SET url_path = {fn_name}(url_path, referer) WHERE domain = ?;"  # noqa: S608
    await db_conn.execute(updates, (MediaFireCrawler.DOMAIN,))
    await db_conn.commit()
