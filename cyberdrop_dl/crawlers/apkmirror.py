from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    dl_btn: str = "a.downloadButton[href*='download/?key=']"
    dl_link: str = "a#download-link"


class APKMirrorCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"APK": "/apk/<developer>/<application>/<release>/<variant>-download"}
    DOMAIN: ClassVar[str] = "apkmirror.com"
    FOLDER_DOMAIN: ClassVar[str] = "APK Mirror"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.apkmirror.com")
    DEFAULT_TRIM_URLS: ClassVar[bool] = False
    _RATE_LIMIT: ClassVar[RateLimit] = 4, 1

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["apk", _, _, _, variant, *_] if variant.endswith("-download"):
                return await self.apk(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def apk(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        dl_url = self.parse_url(css.select(soup, Selector.dl_btn, "href"))
        soup = await self.request_soup(dl_url)
        scrape_item.setup_as_album(self.create_title(_extract_app_name(soup)))

        await asyncio.sleep(min(random.random() * 5, 2))
        cf_redirect = self.parse_url(css.select(soup, Selector.dl_link, "href"))

        async with self.request(cf_redirect, headers={"Referer": str(dl_url)}, impersonate="firefox") as resp:
            src = resp.url

        filename, ext = self.get_filename_and_ext(src.name)
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            src.name,
            ext,
            custom_filename=filename,
            debrid_link=src,
        )


def _extract_app_name(soup: BeautifulSoup) -> str:
    for elem in css.json_ld(soup)["@graph"]:
        if elem.get("@type") == "BreadcrumbList":
            return elem["itemListElement"][2]["name"]

    raise ScrapeError(422, "Unable to extract application name")
