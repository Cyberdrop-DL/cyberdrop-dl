from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper, get_text_between, parse_url

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class Selector:
    BAIT_LINK = "#ideoooolink"
    JS_TOKEN = "script:-soup-contains(ideoooolink)"


class StreamtapeCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Videos": "/v/<video_id>",
        "Player": "/e/<video_id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://streamtape.com")
    DOMAIN: ClassVar[str] = "streamtape.com"
    FOLDER_DOMAIN: ClassVar[str] = "Streamtape"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["e" | "v", video_id, *_]:
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        scrape_item.url = self.PRIMARY_URL / "v" / video_id
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        download_url = _extract_download_link(soup)
        filename, ext = self.get_filename_and_ext(download_url.name)
        return await self.handle_file(download_url, scrape_item, filename, ext)


def _extract_download_link(soup: BeautifulSoup) -> AbsoluteHttpURL:
    script = css.select_one_get_text(soup, Selector.JS_TOKEN)
    token = get_text_between(script, "&token=", "'")
    url = css.select_one_get_text(soup, Selector.BAIT_LINK)
    return parse_url(f"https:/{url}").update_query(token=token)
