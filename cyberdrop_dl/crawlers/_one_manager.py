"""An index and manager of Onedrive based on serverless.

Gitlab: https://git.hit.edu.cn/ysun/OneManager-php
Github: https://github.com/qkqpttgf/OneManager-php
Gitee: https://gitee.com/qkqpttgf/OneManager-php
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler
from cyberdrop_dl.exceptions import InvalidContentTypeError
from cyberdrop_dl.utils import css, error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import Tag

    from cyberdrop_dl.crawlers.crawler import SupportedPaths
    from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem


class Selector:
    TABLE = "table#list-table"
    FILE_LINK = "a.download"
    FOLDER_LINK = "a[name='folderlist']"
    FILE = f"tr:has({FILE_LINK})"
    FOLDER = f"tr:has({FOLDER_LINK})"
    DATE = "td.updated_at"


class OneManagerCrawler(Crawler, is_abc=True):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Any path": "/..."}
    ALLOW_EMPTY_PATH: ClassVar[bool] = True

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        scrape_item.url = scrape_item.url.with_query(None)
        if self.PRIMARY_URL not in scrape_item.parent_threads:
            self._init_item(scrape_item)
        await self._path(scrape_item)

    async def __async_post_init__(self) -> None:
        self.downloader.download_slots = 2

    @error_handling_wrapper
    async def _path(self, scrape_item: ScrapeItem) -> None:
        try:
            soup = await self.request_soup(scrape_item.url)
        except InvalidContentTypeError:  # This is a file, not HTML
            scrape_item.parent_title = scrape_item.parent_title.rsplit("/", 1)[0]
            link = scrape_item.url
            scrape_item.url = link.parent
            return await self._file(scrape_item, link)

        # href are not actual links, they only have the name of the new part
        table = css.select(soup, Selector.TABLE)

        for file in css.iselect(table, Selector.FILE):
            await self.file(scrape_item, file)
            scrape_item.add_children()

        for folder in css.iselect(table, Selector.FOLDER):
            link = scrape_item.url / css.select(folder, Selector.FOLDER_LINK, "href")
            new_item = scrape_item.create_child(link)
            new_item.add_to_parent_title(link.name)
            self.create_task(self.run(new_item))
            scrape_item.add_children()

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, file: Tag) -> None:
        datetime = self.parse_iso_date(css.select_text(file, Selector.DATE))
        link = scrape_item.url / css.select(file, Selector.FILE_LINK, "href")
        await self._file(scrape_item, link, datetime)

    async def _file(self, scrape_item: ScrapeItem, link: AbsoluteHttpURL, uploaded_at: int | None = None) -> None:
        preview_url = link.with_query("preview")  # The query param needs to be `?preview` exactly, with no value or `=`
        new_item = scrape_item.create_child(preview_url)
        new_item.uploaded_at = uploaded_at
        await self.direct_file(new_item, link)

    def _init_item(self, scrape_item: ScrapeItem) -> None:
        scrape_item.setup_as_album(self.FOLDER_DOMAIN, album_id=self.DOMAIN)
        for part in scrape_item.url.parts[1:]:
            scrape_item.add_to_parent_title(part)

        # smugle url as as sentinel
        scrape_item.parent_threads.add(self.PRIMARY_URL)
