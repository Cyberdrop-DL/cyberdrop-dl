from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem

DOWNLOAD_SELECTOR = 'a.btn[href*="md5="]'
HOMEPAGE_CATCHALL_FILE = "/s21/FHVZKQyAZlIsrneDAsp.jpeg"


class FileditchCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File": (
            "/file.php?f=<file_id>",
            "/beta123/<file_id>/<name>",
            "/temp/<file_id>/<name>",
        )
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://fileditchfiles.me/")
    DOMAIN: ClassVar[str] = "fileditch"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [*_, "file.php"]:
                return await self.file(scrape_item)
            case [a, _, *_] if a.startswith(("beta", "temp")):
                return await self.file(scrape_item)
            case _:
                raise ValueError

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        if url.name == "file.php" and (file_id := url.query.get("f")):
            # Their servers accept any number of empty parts before the file
            # Remove them to get a canonical URL
            # https:/fileditchfiles.me////////file.php?f=/b70/1234 -> https:/fileditchfiles.me/file.php?f=/b70/1234
            return (url.origin() / "file.php").with_query(f=file_id)
        return url

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        link_str: str = css.select(soup, DOWNLOAD_SELECTOR, "href")
        link = self.parse_url(link_str)
        if link.path == HOMEPAGE_CATCHALL_FILE:
            raise ScrapeError(422)

        filename, ext = self.get_filename_and_ext(link.name)
        await self.handle_file(link, scrape_item, filename, ext)
