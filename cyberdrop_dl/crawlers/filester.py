from __future__ import annotations

import base64
import dataclasses
import time
from typing import TYPE_CHECKING, ClassVar, Literal, final

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import API, Crawler, DownloadConfig, SupportedPaths, auto_task_id
from cyberdrop_dl.exceptions import PasswordProtectedError
from cyberdrop_dl.network.http import HTTPConfig
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text, open_graph, unique
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


@final
class Selector:
    FILES = ".file-item[onclick]"
    SUBFOLDER = ".subfolder-item[href]"
    NEXT_PAGE = "a.page-link:-soup-contains(→)"
    FILE_DETAILS = "#detailsContent"


@HTTPConfig(rate_limit=(4, 1))
@DownloadConfig(slots=4)
class FilesterCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File": "/d/<slug>",
        "Folder": "/f/<slug>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://filester.me")
    DOMAIN: ClassVar[str] = "filester"

    def __post_init__(self) -> None:
        self.api: FilesterAPI = FilesterAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["d", slug]:
                await self.file(scrape_item, slug)
            case ["f", slug]:
                await self.folder(scrape_item, slug)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, slug: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        await self._file(scrape_item, slug)

    async def _file(self, scrape_item: ScrapeItem, slug: str) -> None:
        soup = await self._request_soup_w_pass(scrape_item.url, scrape_item.password)
        file = await _parse_file(soup)

        if file.hash and await self.check_complete_by_hash(scrape_item.url, file.hash.algo, file.hash.checksum):
            return

        scrape_item.uploaded_at = self.parse_iso_date(file.uploaded_at)
        filename, ext = self.get_filename_and_ext(file.name, mime_type=file.mime_type)

        await self.handle_file(
            scrape_item.url,
            scrape_item,
            file.name,
            ext,
            custom_filename=filename,
            # Downloads expire after 30 minutes so we delay the request for it
            debrid_link=lambda: self.api.download(slug),
            thumbnail=file.thumb,
            metadata=file,
        )

    _file_task = auto_task_id(error_handling_wrapper(_file))

    @error_handling_wrapper
    async def folder(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup, pages = await aio.peek_next(self._folder_pager(scrape_item.url, scrape_item.password))
        title = self.create_title(open_graph.title(soup), album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        downloaded = await self.get_completed_by_album(album_id)
        sleep = aio.periodic_sleep(10)

        async with aio.non_cancelling_taskgroup() as tg:
            async for soup in pages:
                for on_click in unique(css.iselect(soup, Selector.FILES, "onclick")):
                    web_url = self.parse_url(extr_text(on_click, "'", "'"), self.origin)
                    if web_url in downloaded:
                        continue

                    new_item = scrape_item.create_child(web_url)
                    tg.create_task(self._file_task(new_item, web_url.name))
                    scrape_item.add_children()
                    await sleep()

                for subfolder in self.iter_urls(soup, Selector.SUBFOLDER, "href", self.origin):
                    new_item = scrape_item.create_child(subfolder)
                    self.create_task(self.run(new_item))
                    scrape_item.add_children()

    async def _folder_pager(self, url: AbsoluteHttpURL, password: str | None) -> AsyncGenerator[BeautifulSoup]:
        soup = await self._request_soup_w_pass(url, password)
        next_page = url
        while True:
            yield soup
            try:
                query = css.select(soup, Selector.NEXT_PAGE, "href")
            except css.SelectorError:
                break

            next_page = next_page.with_query(query.strip("?"))
            soup = await self.request_soup(next_page)

    async def _request_soup_w_pass(self, url: AbsoluteHttpURL, password: str | None) -> BeautifulSoup:
        url = url.without_query_params("password")
        soup = await self.request_soup(url)
        form = await _extract_form(soup)
        if not form:
            return soup

        if not password:
            raise PasswordProtectedError

        action, nonce = form
        submit_url = self.parse_url(action, self.origin)
        soup = await self.request_soup(
            submit_url,
            "POST",
            data={
                "nonce": nonce,
                "password": _encode_password(password, nonce),
            },
        )
        # Token access is stored in cookies (folder_access_token) in a JWT encoded json (valid for 24hrs)
        if await _extract_form(soup):
            raise PasswordProtectedError("Wrong password")

        if submit_url.path != url.path:
            # The submit URL for files is actually their folder. Remake request to the actual file page
            soup = await self.request_soup(url)
            assert await _extract_form(soup) is None
        return soup


@dataclasses.dataclass(slots=True)
class Hash:
    algo: Literal["md5", "sha256"]
    checksum: str


@dataclasses.dataclass(slots=True)
class File:
    name: str
    uploaded_at: str
    mime_type: str
    thumb: str | None
    hash: Hash | None = None


class FilesterAPI(API):
    async def download(self, slug: str) -> AbsoluteHttpURL:
        api_url = self.origin / "v2/api/public/download"
        resp = await self.request_json(api_url, method="POST", json={"file_slug": slug})
        dl_link = self.parse_url(resp["server"]) / "v2" / resp["file"]
        return dl_link.with_query(token=resp["token"], download="true")


def _encode_password(password: str, nonce: str) -> str:
    now = int(time.time() * 1000)
    payload = f"{password}|{now}|{nonce}"
    return base64.urlsafe_b64encode(payload.encode()).decode()


@aio.to_thread
def _extract_form(soup: BeautifulSoup) -> tuple[str, str] | None:
    try:
        form = css.select(soup, "#password-form")
    except css.SelectorError:
        return None
    return css.attr(form, "action"), css.select(form, "#nonce", "value")


@aio.to_thread
def _parse_file(soup: BeautifulSoup) -> File:
    file_details = css.select(soup, Selector.FILE_DETAILS)

    def file_attr(name: str) -> str:
        return css.select_text(file_details, f"span:-soup-contains({name}) + span")

    def file_hash() -> Hash | None:
        for name, attr in (("sha256", "SHA-256"), ("md5", "MD5")):
            try:
                return Hash(name, file_attr(attr))  # pyright: ignore[reportArgumentType]
            except css.SelectorError:
                pass

    return File(
        name=open_graph.title(soup),
        hash=file_hash(),
        uploaded_at=file_attr("Uploaded"),
        mime_type=file_attr("Type"),
        thumb=open_graph.get_image(soup),
    )
