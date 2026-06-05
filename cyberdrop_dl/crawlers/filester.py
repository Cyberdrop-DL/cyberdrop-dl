from __future__ import annotations

import base64
import dataclasses
import random
import time
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import API, Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.exceptions import PasswordProtectedError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper, extr_text, open_graph

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator, Iterable

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem

_CDN_URLS = AbsoluteHttpURL("https://cache1.filester.me"), AbsoluteHttpURL("https://cache6.filester.me")


class Selector:
    FILES = ".file-item[onclick]"
    SUBFOLDER = ".subfolder-item[href]"
    NEXT_PAGE = "a.page-link:-soup-contains(→)"
    FILE_DETAILS = "#detailsContent"


class FilesterCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File": "/d/<slug>",
        "Folder": "/f/<slug>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://filester.me")
    DOMAIN: ClassVar[str] = "filester"
    _RATE_LIMIT: ClassVar[RateLimit] = 4, 1

    def __post_init__(self) -> None:
        self.api: FilesterAPI = FilesterAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["d", slug]:
                return await self.file(scrape_item, slug)
            case ["f", slug]:
                return await self.folder(scrape_item, slug)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, slug: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self._request_soup_w_pass(scrape_item.url, scrape_item.password)
        file = _parse_file(soup)
        scrape_item.uploaded_at = self.parse_iso_date(file.uploaded_at)
        filename, ext = self.get_filename_and_ext(file.name, mime_type=file.mime_type)
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            file.name,
            ext,
            custom_filename=filename,
            debrid_link=await self.api.download(slug),
        )

    @error_handling_wrapper
    async def folder(self, scrape_item: ScrapeItem, album_id: str) -> None:
        title: str = ""
        subfolders: list[str] = []

        async for soup in self._folder_pager(scrape_item.url, scrape_item.password):
            if not title:
                name = open_graph.title(soup)
                title = self.create_title(name, album_id)
                scrape_item.setup_as_album(title, album_id=album_id)

            self._iter_children(scrape_item, _extract_files(soup))
            subfolders.extend(_extract_subfolders(soup))

        self._iter_children(scrape_item, dict.fromkeys(subfolders))

    def _iter_children(self, scrape_item: ScrapeItem, children: Iterable[str]) -> None:
        for child in children:
            web_url = self.parse_url(child, self.origin)
            new_scrape_item = scrape_item.create_child(web_url)
            self.create_task(self.run(new_scrape_item))
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
        form = _extract_form(soup)
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
        if _extract_form(soup):
            raise PasswordProtectedError("Wrong password")
        if submit_url.path != url.path:
            # The submit URL for files is actually their folder. Remake request to the actual file page
            soup = await self.request_soup(url)
            assert _extract_form(soup) is None
        return soup


@dataclasses.dataclass(slots=True)
class File:
    name: str
    uploaded_at: str
    mime_type: str
    hash_algo: str
    checksum: str


class FilesterAPI(API):
    async def download(self, slug: str) -> AbsoluteHttpURL:
        api_url = self.origin / "api/public/download"
        resp = await self.request_json(api_url, method="POST", json={"file_slug": slug})
        dl_link = random.choice(_CDN_URLS).with_path(resp["download_url"])
        return dl_link.with_query(download="true")


def _encode_password(password: str, nonce: str) -> str:
    now = int(time.time() * 1000)
    payload = f"{password}|{now}|{nonce}"
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _extract_form(soup: BeautifulSoup) -> tuple[str, str] | None:
    try:
        form = css.select(soup, "#password-form")
    except css.SelectorError:
        return None
    return css.attr(form, "action"), css.select(form, "#nonce", "value")


def _extract_files(soup: BeautifulSoup) -> Generator[str]:
    for on_click in css.iselect(soup, Selector.FILES, "onclick"):
        yield extr_text(on_click, "'", "'")


def _extract_subfolders(soup: BeautifulSoup) -> Generator[str]:
    return css.iselect(soup, Selector.SUBFOLDER, "href")


def _parse_file(soup: BeautifulSoup) -> File:
    file_details = css.select(soup, Selector.FILE_DETAILS)

    def file_attr(name: str) -> str:
        return css.select_text(file_details, f"span:-soup-contains({name}) + span")

    try:
        hash_algo, checksum = "sha256", file_attr("SHA-256")
    except css.SelectorError:
        hash_algo, checksum = "md5", file_attr("MD5")

    return File(
        name=open_graph.title(soup),
        hash_algo=hash_algo,
        checksum=checksum,
        uploaded_at=file_attr("Uploaded"),
        mime_type=file_attr("Type"),
    )
