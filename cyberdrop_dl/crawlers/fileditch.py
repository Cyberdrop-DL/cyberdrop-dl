from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import DDOSGuardError, ScrapeError
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem

DOWNLOAD_SELECTOR = 'a.btn[href*="md5="]'
HOMEPAGE_CATCHALL_FILE = "/s21/FHVZKQyAZlIsrneDAsp.jpeg"
TURNSTILE_CHALLENGE_SELECTOR = "script[src*='challenges.cloudflare.com/turnstile'], .cf-turnstile, #turnstile-wrapper"

PRIMARY_URL = AbsoluteHttpURL("https://fileditchfiles.me/")


def _check_turnstile(soup: BeautifulSoup) -> None:
    """Detect Cloudflare Turnstile challenge pages served with HTTP 200."""
    if soup.select_one(TURNSTILE_CHALLENGE_SELECTOR):
        raise DDOSGuardError("Cloudflare Turnstile challenge detected on Fileditch")


class FileditchCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Direct links": ""}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "fileditch"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if scrape_item.url.path != "/file.php":
            # Some old files are only direct linkable
            return await self.direct_file(scrape_item)
        return await self.file(scrape_item)

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)
        _check_turnstile(soup)
        link_str: str = css.select(soup, DOWNLOAD_SELECTOR, "href")
        link = self.parse_url(link_str)
        if link.path == HOMEPAGE_CATCHALL_FILE:
            raise ScrapeError(422)
        filename, ext = self.get_filename_and_ext(link.name)
        await self.handle_file(link, scrape_item, filename, ext)
