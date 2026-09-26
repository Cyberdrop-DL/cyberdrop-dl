from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, ClassVar, final

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text, open_graph, parse_url
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


@final
class Selector:
    BAIT_LINK = "#ideoooolink"
    JS_TOKEN = "script:-soup-contains(ideoooolink)"  # noqa: S105


class StreamtapeCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Videos": (
            "/v/<video_id>",
            "/e/<video_id>",
        )
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://streamtape.com")
    DOMAIN: ClassVar[str] = "streamtape.com"
    FOLDER_DOMAIN: ClassVar[str] = "Streamtape"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["e" | "v", video_id, *_]:
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        scrape_item.url = self.PRIMARY_URL / "v" / video_id
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        link = await asyncio.to_thread(_extract_dl_url, soup)
        name = open_graph.title(soup)
        _, ext = self.get_filename_and_ext(name)
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            name,
            ext,
            debrid_link=link,
            custom_filename=self.create_custom_filename(name, ext, file_id=video_id),
        )


def _extract_dl_url(soup: BeautifulSoup) -> AbsoluteHttpURL:
    script = css.select_text(soup, Selector.JS_TOKEN)
    token = extr_text(script, "&token=", "'")
    bait_url = css.select_text(soup, Selector.BAIT_LINK)
    return parse_url(f"https:/{bait_url}").update_query(token=token)
