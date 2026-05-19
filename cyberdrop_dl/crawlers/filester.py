from __future__ import annotations

import random
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper, extr_text, open_graph

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

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

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["d", slug]:
                return await self.file(scrape_item, slug)
            case ["f", slug]:
                return await self.folder(scrape_item, slug)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def folder(self, scrape_item: ScrapeItem, album_id: str) -> None:
        title: str = ""
        subfolders: list[str] = []

        async for soup in self._folder_pager(scrape_item.url):
            if not title:
                name = open_graph.title(soup)
                title = self.create_title(name, album_id)
                scrape_item.setup_as_album(title, album_id=album_id)

            for on_click in css.iselect(soup, Selector.FILES, "onclick"):
                web_url = self.parse_url(extr_text(on_click, "'", "'"))
                new_scrape_item = scrape_item.create_child(web_url)
                self.create_task(self.run(new_scrape_item))
                scrape_item.add_children()

            subfolders.extend(css.iselect(soup, Selector.SUBFOLDER, "href"))

        for subfolder in dict.fromkeys(subfolders):
            new_scrape_item = scrape_item.create_child(self.parse_url(subfolder))
            self.create_task(self.run(new_scrape_item))
            scrape_item.add_children()

    async def _folder_pager(self, url: AbsoluteHttpURL) -> AsyncGenerator[BeautifulSoup]:
        next_page = url
        while True:
            soup = await self.request_soup(next_page)
            yield soup
            try:
                query = css.select(soup, Selector.NEXT_PAGE, "href")
            except css.SelectorError:
                break

            next_page = next_page.with_query(query.strip("?"))

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, slug: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        file_details = css.select(soup, Selector.FILE_DETAILS)

        def file_attr(name: str) -> str:
            return css.select_text(file_details, f"span:-soup-contains({name}) + span")

        try:
            hash_algo, checksum = "sha256", file_attr("SHA-256")
        except css.SelectorError:
            hash_algo, checksum = "md5", file_attr("MD5")

        if await self.check_complete_by_hash(scrape_item, hash_algo, checksum):
            return

        scrape_item.uploaded_at = self.parse_iso_date(file_attr("Uploaded"))
        filename = open_graph.title(soup)
        custom_filename, ext = self.get_filename_and_ext(filename, mime_type=file_attr("Type"))
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            filename,
            ext,
            custom_filename=custom_filename,
            debrid_link=await self._request_download(slug),
        )

    async def _request_download(self, slug: str) -> AbsoluteHttpURL:
        resp = await self.request_json(
            self.PRIMARY_URL / "api/public/download",
            method="POST",
            json={"file_slug": slug},
        )
        dl_link = random.choice(_CDN_URLS).with_path(resp["download_url"])
        return dl_link.with_query(download="true")
