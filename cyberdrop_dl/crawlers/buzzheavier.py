from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class BuzzHeavierCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Direct links": ""}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://buzzheavier.com")
    DOMAIN: ClassVar[str] = "buzzheavier.com"
    FOLDER_DOMAIN: ClassVar[str] = "BuzzHeavier"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        return await self.file(scrape_item)

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url, impersonate=True)
        name = css.select_text(soup, ".file-name")
        date = css.select_text(soup, "p:-soup-contains-own(Uploaded)").rpartition("Uploaded")[-1].strip()
        scrape_item.uploaded_at = self.parse_date(date, "%B %d, %Y")
        hx_url = self.parse_url(css.select(soup, ".download-btn", "hx-get"))
        async with self.request(
            hx_url,
            method="HEAD",
            headers={
                "HX-Current-URL": str(scrape_item.url),
                "HX-Request": "true",
            },
        ) as resp:
            src = self.parse_url(resp.headers["hx-redirect"])

        filename, ext = self.get_filename_and_ext(name, assume_ext=".zip")
        await self.handle_file(scrape_item.url, scrape_item, filename, ext, debrid_link=src)
