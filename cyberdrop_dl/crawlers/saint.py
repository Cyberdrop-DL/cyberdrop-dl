from __future__ import annotations

import base64
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper, get_text_between

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class Selector:
    VIDEOS = "a.action.download"
    EMBED_SRC = css.CssAttributeSelector("#main-video source", "src")
    DOWNLOAD_BUTTON = css.CssAttributeSelector("a:-soup-contains('Download Video')", "href")
    NOT_FOUND_IMAGE = "#video-container img[src*='assets/notfound.gif']"


class SaintCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "saint2.su", "saint2.cr"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/a/...",
        "Video": (
            "/embed/...",
            "/d/...",
        ),
        "Direct links": "",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://saint2.su/")
    DOMAIN: ClassVar[str] = "saint"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["a", album_id, *_]:
                return await self.album(scrape_item, album_id)
            case ["embed" | "d", _, *_]:
                return await self.video(scrape_item)
            case ["data", _, *_]:
                return await self.direct_file(scrape_item)

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        results = await self.get_album_results(album_id)
        soup = await self.request_soup(scrape_item.url)

        title_portion = css.select_one_get_text(soup, "title").rsplit(" - Saint Video Hosting")[0].strip()
        if not title_portion:
            title_portion = scrape_item.url.name
        title = self.create_title(title_portion, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        for video in soup.select(Selector.VIDEOS):
            on_click_text: str = css.get_attr(video, "onclick")
            link_str = get_text_between(on_click_text, "('", "');")
            link = self.parse_url(link_str)
            if not self.check_album_results(link, results):
                new_scrape_item = scrape_item.create_child(link)
                self.create_task(self.run(new_scrape_item))
                scrape_item.add_children()

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        link = await self._get_download_url(scrape_item.url)
        await self.direct_file(scrape_item, link)

    async def _get_download_url(self, web_url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        soup = await self.request_soup(web_url)
        for selector in (Selector.EMBED_SRC, Selector.DOWNLOAD_BUTTON):
            try:
                return self.parse_url(selector(soup))
            except css.SelectorError:
                continue

        if _is_not_found(soup):
            raise ScrapeError(404)
        raise ScrapeError(422, "Couldn't find video source")

    def parse_url(
        self, link_str: str, relative_to: AbsoluteHttpURL | None = None, *, trim: bool | None = None
    ) -> AbsoluteHttpURL:
        link = super().parse_url(link_str, relative_to, trim=trim)
        if base64_str := link.query.get("file"):
            filename = base64.b64decode(base64_str).decode("utf-8")
            return link.origin() / "videos" / filename

        return link


def _is_not_found(soup: BeautifulSoup) -> bool:
    title = soup.select_one("title")
    return bool(
        (title and title.get_text() == "Video not found")
        or soup.select_one(Selector.NOT_FOUND_IMAGE)
        or "File not found in the database" in soup.get_text()
    )
