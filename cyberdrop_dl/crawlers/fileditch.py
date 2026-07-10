from __future__ import annotations

import json
from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text, parse_url
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


_HOMEPAGE_CATCH_ALL = "/s21/FHVZKQyAZlIsrneDAsp.jpeg"


class FileditchCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File": (
            "/file.php?f=<file_id>",
            "/beta123/<file_id>/<name>",
            "/temp/<file_id>/<name>",
            "/alpha7/<file_id>/<name>",
        )
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://fileditchfiles.me/")
    DOMAIN: ClassVar[str] = "fileditch"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [*_, "file.php"]:
                return await self.file(scrape_item)
            case [a, _, *_] if a.startswith(("beta", "temp", "alpha")):
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
        if soup.select_one(".gone-path"):
            raise ScrapeError(410)
        src = _extract_dl_url(soup)
        if src.path == _HOMEPAGE_CATCH_ALL:
            raise ScrapeError(422)

        filename, ext = self.get_filename_and_ext(src.name)
        await self.handle_file(src, scrape_item, filename, ext)


def _extract_dl_url(soup: BeautifulSoup) -> AbsoluteHttpURL:
    js_join = '].join("")'
    js_text = css.select_text(soup, f"script:-soup-contains-own('{js_join}')")
    array = extr_text(js_text, "= [", js_join)
    try:
        return _parse_url_parts(f"[{array}]")
    except ValueError as e:
        raise ScrapeError(422, "Unable to extract download URL") from e


def _parse_url_parts(js_array: str) -> AbsoluteHttpURL:
    parts: list[str] = json.loads(js_array)
    url = parse_url("".join(parts), trim=False)
    if not (url.query.get("md5") and url.query.get("expires")):
        raise ValueError(url)
    return url
