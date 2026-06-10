from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper, open_graph, parse_url

if TYPE_CHECKING:
    from collections.abc import Generator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


class NaughtyMachinimaCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/video/<slug>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.naughtymachinima.com")
    DOMAIN: ClassVar[str] = "naughtymachinima"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video", video_id, _]:
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        name = open_graph.title(soup)
        date = css.json_ld(soup, "uploadDate")["uploadDate"]
        scrape_item.uploaded_at = self.parse_iso_date(date)
        res, src = max(_extract_sources(soup))
        filename = self.create_custom_filename(name, ext := ".mp4", resolution=res, file_id=video_id)
        await self.handle_file(src, scrape_item, name, ext, custom_filename=filename)


def _extract_sources(soup: BeautifulSoup) -> Generator[tuple[int, AbsoluteHttpURL]]:
    for src in css.iselect(soup, "video#vjsplayer source"):
        res = int(css.attr(src, "res"))
        url = parse_url(css.attr(src, "src"))
        yield res, url
