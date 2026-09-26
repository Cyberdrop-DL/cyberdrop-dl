from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class BuzzHeavierCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "bzzhr.co", "bzzhr.to", "buzzheavier.com", "fuckingfast.net"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"File": "/<file_id>"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://buzzheavier.com")
    DOMAIN: ClassVar[str] = "buzzheavier.com"
    FOLDER_DOMAIN: ClassVar[str] = "BuzzHeavier"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_]:
                await self.file(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete(scrape_item.url):
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


class FuckingFastCrawler(Crawler):
    # Mirror exclusive for Fitgirl, but links are not interchangable
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"File": "/<file_id>"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://fuckingfast.co")
    DOMAIN: ClassVar[str] = "fuckingfast.co"
    FOLDER_DOMAIN: ClassVar[str] = "FuckingFast"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_]:
                await self.file(scrape_item)
            case _:
                raise ValueError

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        return super().transform_url(url).with_fragment(None)

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        resp = await self.flaresolverr_request(scrape_item.url)
        soup = await resp.soup()
        name = css.page_title(soup)
        hx_url = self.parse_url(css.select(soup, ".link-button", "hx-post"))
        async with self.request(
            hx_url,
            method="POST",
            headers={
                "HX-Current-URL": str(scrape_item.url),
                "HX-Request": "true",
            },
        ) as resp:
            src = self.parse_url(resp.headers["hx-redirect"])

        filename, ext = self.get_filename_and_ext(name, assume_ext=".zip")
        await self.handle_file(scrape_item.url, scrape_item, name, ext, debrid_link=src, custom_filename=filename)
