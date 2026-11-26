from __future__ import annotations

import asyncio
import itertools
from typing import TYPE_CHECKING, Any, ClassVar, Literal, final

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths, auto_task_id
from cyberdrop_dl.exceptions import DDOSGuardError, PasswordProtectedError, ScrapeError
from cyberdrop_dl.network.http import HTTPConfig
from cyberdrop_dl.utils import css, dates, extr_text
from cyberdrop_dl.utils.dataclass import struct
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.urls import parse_http_url

if TYPE_CHECKING:
    from collections.abc import Iterable

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem


@final
class Selector:
    DOWNLOAD = css.Selector(
        ", ".join(
            (
                ".btn-group.responsiveMobileMargin button:-soup-contains('Download')[onclick*='download_token']",
                ".dropdown-menu.dropdown-info a[onclick*='download_token']",
            )
        ),
        attribute="onclick",
    )
    FILE_NAME = ".image-name-title"
    FILE_UPLOAD_DATE = "td:-soup-contains('Uploaded:') + td"
    FILE_INFO = "script:-soup-contains('showFileInformation')"

    LOAD_IMAGES = "div[class*='page-container'] script:-soup-contains('loadImages')"
    FOLDER_ID = css.Selector("#folderId", "value")
    FOLDER_ITEM = "#fileListing [class*=fileItem]"
    FOLDER_TOTAL_PAGES = css.Selector("input#rspTotalPages", "value")

    LOGIN_FORM = "form#form_login"
    PASSWORD_PROTECTED = "#folderPasswordForm, #filePassword"  # noqa: S105
    RECAPTCHA = "form[method=POST] script[src*='/recaptcha/api.js']"


@HTTPConfig(rate_limit=(5, 1))
class YetiShareCrawler(Crawler, is_abc=True):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Files": (
            "/<file_id>",
            "/<file_id>/<file_name>",
        ),
        "Public Folders": (
            "/folder/<folder_id>",
            "/folder/<folder_id>/<folder_name>",
        ),
        "Shared folders": "/shared/<share_key>",
    }

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.FOLDERS_API_URL: AbsoluteHttpURL = cls.PRIMARY_URL / "account/ajax/load_files"
        cls.FILE_API_URL: AbsoluteHttpURL = cls.PRIMARY_URL / "account/ajax/file_details"
        cls.FOLDER_PASSWORD_API_URL: AbsoluteHttpURL = cls.PRIMARY_URL / "ajax/folder_password_process"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["folder", folder_id, *_]:
                await self.folder(scrape_item, folder_id)
            case ["shared", folder_id]:
                await self.folder(scrape_item, folder_id, is_shared=True)
            case [file_id]:
                await self.file(scrape_item, file_id)
            case [file_id, _]:
                await self.file(scrape_item, file_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def folder(self, scrape_item: ScrapeItem, folder_id: str, *, is_shared: bool = False) -> None:
        # Make request to update cookies. Access to folders is saved in cookies
        soup = await self.request_soup(scrape_item.url)

        if soup.select_one(Selector.LOGIN_FORM):
            raise ScrapeError(410, "Folder has been deleted")

        if is_shared:
            page_type = "nonaccountshared"
            node_id = ""

        else:
            # this looks like:  loadImages('folder', '12345', 1, 0, '', {'searchTerm': "", 'filterUploadedDateRange': ""});
            page_type = "folder"
            node_id = await _extr_node_id(soup)

        page = 1
        total_pages = None
        if not scrape_item.album_id:
            scrape_item.setup_as_album("", album_id=folder_id)

        if not is_shared:
            title = (await aio.to_thread(css.page_title)(soup, self.DOMAIN)).removesuffix("Folder").strip()
            scrape_item.append_folders(self.create_title(title, folder_id))

        sleep = aio.periodic_sleep(10)
        for page in itertools.count(1):
            ajax_soup = await self._get_soup_from_ajax_api(
                scrape_item,
                data={
                    "pageType": page_type,
                    "perPage": 0,
                    "filterOrderBy": "",
                    "nodeId": node_id,
                    "pageStart": page,
                },
            )

            if total_pages is None:
                total_pages = int(await asyncio.to_thread(css.select, ajax_soup, Selector.FOLDER_TOTAL_PAGES))

            async with aio.non_cancelling_taskgroup() as tg:
                async for item in _extr_items(ajax_soup):
                    new_item = scrape_item.create_child(self.parse_url(item.url))
                    if item.type == "file":
                        content_id = int(item.id)
                        new_item.part_of_album = not is_shared
                        tg.create_task(self._handle_content_id_task(new_item, content_id))
                        scrape_item.add_children()
                    else:
                        self.create_task(self.run(new_item))
                    await sleep()

            if page >= total_pages:
                break

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, file_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        if soup.select_one(Selector.PASSWORD_PROTECTED):
            soup = await self._unlock_password_protected_file(scrape_item, file_id)

        await _check_is_available(soup)
        content_id = await _extr_content_id(soup)
        await self._handle_content_id(scrape_item, content_id)

    @error_handling_wrapper
    async def _handle_content_id(self, scrape_item: ScrapeItem, content_id: int) -> None:
        soup = await self._get_soup_from_ajax_api(
            scrape_item,
            data={"u": content_id},
            is_file=True,
        )
        file = await _extr_download(soup)
        scrape_item.uploaded_at = file.uploaded_at
        custom_filename, ext = self.get_filename_and_ext(file.name)
        await self.handle_file(file.src, scrape_item, file.name, ext, custom_filename=custom_filename)

    _handle_content_id_task = auto_task_id(_handle_content_id)

    async def _get_soup_from_ajax_api(
        self, scrape_item: ScrapeItem, data: dict[str, Any], *, is_file: bool = False
    ) -> BeautifulSoup:
        async def ajax_api_request() -> BeautifulSoup:
            ajax_url = self.FILE_API_URL if is_file else self.FOLDERS_API_URL
            json_resp: dict[str, str] = await self.request_json(
                ajax_url,
                method="POST",
                data=data,
                headers={"X-Requested-With": "XMLHttpRequest"},
            )

            return await css.asoup(json_resp["html"].replace("\\", ""))

        soup = await ajax_api_request()
        if soup.select_one(Selector.PASSWORD_PROTECTED):
            node_id = data.get("nodeId") or await css.aselect(soup, Selector.FOLDER_ID)
            await self._unlock_password_protected_folder(scrape_item, node_id)
            soup = await ajax_api_request()

        await _check_is_available(soup)
        return soup

    async def _unlock_password_protected_file(self, scrape_item: ScrapeItem, file_id: str) -> BeautifulSoup:
        if not scrape_item.password:
            raise PasswordProtectedError

        password_post_url = (self.PRIMARY_URL / file_id).with_query("pt=")

        soup = await self.request_soup(
            password_post_url,
            method="POST",
            data={
                "filePassword": scrape_item.password,
                "submitme": 1,
            },
        )

        if soup.select_one(Selector.PASSWORD_PROTECTED):
            raise PasswordProtectedError("File password is invalid")
        return soup

    async def _unlock_password_protected_folder(self, scrape_item: ScrapeItem, node_id: str) -> None:
        if not scrape_item.password:
            raise PasswordProtectedError

        # Make a request with the password. Access to the file/folder will be stored in cookies
        json_resp: dict[str, Any] = await self.request_json(
            self.FOLDER_PASSWORD_API_URL,
            method="POST",
            data={
                "folderPassword": scrape_item.password,
                "folderId": node_id,
                "submitme": 1,
            },
        )
        if not json_resp.get("success"):
            raise PasswordProtectedError(message="Incorrect password")


@aio.to_thread
def _extr_node_id(soup: BeautifulSoup) -> str:
    load_images = extr_text(soup.select(Selector.LOAD_IMAGES)[-1].text, "loadImages(", ");")
    return load_images.replace("'", "").split(",")[1].strip()


@aio.to_thread
def _extr_content_id(soup: BeautifulSoup) -> int:
    return int(extr_text(css.select_text(soup, Selector.FILE_INFO), "showFileInformation(", ");"))


@struct
class FileDownload:
    name: str
    uploaded_at: int
    src: AbsoluteHttpURL


@aio.to_thread
def _extr_download(soup: BeautifulSoup) -> FileDownload:
    uploaded = dates.parse_format(css.select_text(soup, Selector.FILE_UPLOAD_DATE), "%d/%m/%Y %H:%M:%S")
    on_click = css.select(soup, Selector.DOWNLOAD)
    # Manually parse link. Some URLs are invalid. ex: https://cyberfile.me/7cfu
    # For the download URL, the slug does not actually matter. It can be anything
    src = extr_text(on_click, "('", "');")
    token = src.rpartition("download_token=")[-1]
    return FileDownload(
        src=parse_http_url(src).with_query(download_token=token),
        uploaded_at=int(uploaded.timestamp()),
        name=css.select_text(soup, Selector.FILE_NAME),
    )


@struct
class Item:
    id: str
    url: str
    type: Literal["file", "folder"]


@aio.iterable_to_thread
def _extr_items(soup: BeautifulSoup) -> Iterable[Item]:
    for item in css.iselect(soup, Selector.FOLDER_ITEM):
        try:
            content_id = css.attr(item, "fileid")
        except css.SelectorError:
            kind = "folder"
            content_id = css.attr(item, "folderid")
            url = css.attr(item, "sharing-url")
        else:
            kind = "file"
            url = css.attr(item, "dtfullurl")

        yield Item(id=content_id, url=url, type=kind)


@aio.to_thread
def _check_is_available(soup: BeautifulSoup) -> None:
    if soup.select_one(Selector.RECAPTCHA):
        raise DDOSGuardError("Google recaptcha found")

    content = soup.get_text()

    if "File has been removed" in content:
        raise ScrapeError(410)

    if "File is not publicly available" in content:
        raise ScrapeError(401)
