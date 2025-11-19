from __future__ import annotations

import base64
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper, get_text_between, parse_url

if TYPE_CHECKING:
    from bs4 import BeautifulSoup, Tag

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class Selector:
    VIDEOS_PLAY = "a.action.play"
    VIDEOS_DOWNLOAD = "a.action.download"
    EMBED_SRC = css.CssAttributeSelector("#main-video source", "src")
    DOWNLOAD_BTN = css.CssAttributeSelector("a:-soup-contains('Download Video')", "href")
    NOT_FOUND_IMAGE = "#video-container img[src*='assets/notfound.gif']"


class SaintCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "saint2.su", "saint2.cr"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/a/...",
        "Video": (
            "/embed/...",
            "/d/...",
        ),
        "Direct links": (
            "/data/...",
            "/videos/...",
        ),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://saint2.su/")
    DOMAIN: ClassVar[str] = "saint"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["a", album_id, *_]:
                return await self.album(scrape_item, album_id)
            case ["embed" | "d", _, *_]:
                return await self.video(scrape_item)
            case ["data" | "videos", _, *_]:
                return await self.direct_file(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        name = css.page_title(soup).removesuffix(" - Saint Video Hosting")
        title = self.create_title(name, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        for download, play in zip(
            soup.select(Selector.VIDEOS_DOWNLOAD),
            soup.select(Selector.VIDEOS_PLAY),
            strict=True,
        ):
            web_url = _select_on_click(download)
            source = _select_on_click(play)
            new_scrape_item = scrape_item.create_child(web_url)
            self.create_task(self.direct_file(new_scrape_item, source))
            scrape_item.add_children()

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        link = _select_download_url(soup)
        await self.direct_file(scrape_item, link)

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


def _select_on_click(tag: Tag) -> AbsoluteHttpURL:
    on_click = css.get_attr(tag, "onclick")
    link_str = get_text_between(on_click, "('", "');")
    return parse_url(link_str)


def _select_download_url(soup: BeautifulSoup) -> AbsoluteHttpURL:
    for selector in (Selector.EMBED_SRC, Selector.DOWNLOAD_BTN):
        try:
            return parse_url(selector(soup))
        except css.SelectorError:
            continue

    if _is_not_found(soup):
        raise ScrapeError(404)
    raise ScrapeError(422, "Couldn't find video source")
