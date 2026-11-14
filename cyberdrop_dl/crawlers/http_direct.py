from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl.constants import FileExt
from cyberdrop_dl.crawlers.crawler import Crawler
from cyberdrop_dl.downloader.http import Downloader
from cyberdrop_dl.exceptions import NoExtensionError
from cyberdrop_dl.filepath import get_filename_and_ext
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


@Crawler.db_path_builder("url")
class DirectHttpFileCrawler(Crawler, is_generic=True):
    DOMAIN: ClassVar[str] = "no_crawler"

    async def __async_post_init__(self) -> None:
        self.downloader = Downloader(self.manager, domain=self.DOMAIN)
        self.downloader.log_prefix = "Download attempt (unsupported domain)"

    @override
    async def fetch(self, scrape_item: ScrapeItem) -> None:
        try:
            filename, ext = get_filename_and_ext(scrape_item.url.name)
        except NoExtensionError:
            filename, ext = get_filename_and_ext(scrape_item.url.name, xenforo=True)

        if ext in FileExt.MEDIA:
            coro = self.file(scrape_item, filename, ext)
        elif ext == ".m3u8":
            coro = self.m3u8(scrape_item)
        else:
            raise ValueError

        self.create_eager_task(coro)

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, filename: str, ext: str) -> None:
        await self.handle_file(scrape_item.url, scrape_item, scrape_item.url.name, ext, custom_filename=filename)

    async def m3u8(self, scrape_item: ScrapeItem) -> None:
        with self.new_task_id(scrape_item.url):
            await self.generic_m3u8(scrape_item)
