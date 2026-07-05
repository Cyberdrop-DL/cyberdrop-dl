from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    FILES = css.CssAttributeSelector(".file-actions button[data-url][data-filename]", "data-url")
    DOWNLOAD_BUTTON = css.CssAttributeSelector("a#downloadButton", "href")


class AnonTransferCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File": "/d/<file_id>",
        "Folder": "/f/<folder_uuid>",
        "Direct Link": (
            "/download-direct.php?dir=<file_id>&file=<filename>",
            "/uploads/<file_id>/<filename>",
        ),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://anontransfer.com")
    DOMAIN: ClassVar[str] = "anontransfer.com"

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        dir_ = url.query.get("dir")
        file = url.query.get("file")
        if dir_ and file:
            return cls.PRIMARY_URL / "uploads" / dir_ / file
        return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["d", _]:
                return await self.file(scrape_item)
            case ["uploads", _, _]:
                return await self.direct_file(scrape_item)
            case ["f", folder_id]:
                return await self.folder(scrape_item, folder_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def folder(self, scrape_item: ScrapeItem, folder_id: str) -> None:
        title = self.create_title(folder_id, folder_id)
        scrape_item.setup_as_album(title, album_id=folder_id)
        soup = await self.request_soup(scrape_item.url)

        should_download = await self.make_album_checker(folder_id)
        urls = map(self.transform_url, self.iter_urls(soup, *Selector.FILES))
        for file in filter(should_download, urls):
            file = self.transform_url(file)
            self.create_eager_task(self.direct_file(scrape_item, file))
            scrape_item.add_children()

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)
        src = self.parse_url(Selector.DOWNLOAD_BUTTON(soup))
        await self.direct_file(scrape_item, self.transform_url(src))
