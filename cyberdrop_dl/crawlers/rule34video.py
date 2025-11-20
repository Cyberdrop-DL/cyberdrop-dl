from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._kvs import KernelVideoSharingCrawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.crawlers.crawler import SupportedPaths
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


PRIMARY_URL = AbsoluteHttpURL("https://rule34video.com/")
DOWNLOADS_SELECTOR = "div#tab_video_info div.row_spacer div.wrap > a.tag_item"
VIDEO_TITLE_SELECTOR = "h1.title_video"

PLAYLIST_ITEM_SELECTOR = "div.item.thumb > a.th"
PLAYLIST_NEXT_PAGE_SELECTOR = "div.item.pager.next > a"
PLAYLIST_TITLE_SELECTORS = {
    "tags": "h1.title:-soup-contains('Tagged with')",
    "search": "h1.title:-soup-contains('Videos for:')",
    "members": "div.channel_logo > h2.title",
    "models": "div.brand_inform > div.title",
}

PLAYLIST_TITLE_SELECTORS["categories"] = PLAYLIST_TITLE_SELECTORS["models"]
TITLE_TRASH = "Tagged with", "Videos for:"


class Rule34VideoCrawler(KernelVideoSharingCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Members": "/members/...",
        "Models": "/models/...",
        "Search": "/search/...",
        "Tags": "/tags/...",
        "Video": (
            "/video/<id>/<name>",
            "/videos/<id>/<name>",
        ),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    NEXT_PAGE_SELECTOR: ClassVar[str] = PLAYLIST_NEXT_PAGE_SELECTOR
    DOMAIN: ClassVar[str] = "rule34video"
    FOLDER_DOMAIN: ClassVar[str] = "Rule34Video"

    async def async_startup(self) -> None:
        self.update_cookies({"kt_rt_popAccess": 1, "kt_tcookie": 1})

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video" | "videos", _, *_]:
                return await self.video(scrape_item)
            case ["tags" | "search" | "members" | "models" as type_, _, *_]:
                return await self.playlist(scrape_item, type_)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def playlist(self, scrape_item: ScrapeItem, playlist_type: str) -> None:
        title: str = ""
        async for soup in self.web_pager(scrape_item.url):
            if not title:
                title = get_playlist_title(soup, playlist_type)
                title = self.create_title(title)
                scrape_item.setup_as_album(title)

            for _, new_scrape_item in self.iter_children(scrape_item, soup, PLAYLIST_ITEM_SELECTOR):
                self.create_task(self.run(new_scrape_item))


def get_playlist_title(soup: BeautifulSoup, playlist_type: str) -> str:
    assert playlist_type
    selector = PLAYLIST_TITLE_SELECTORS[playlist_type]
    title_tag = css.select_one(soup, selector)
    if playlist_type in ("tags", "search"):
        for span in title_tag.select("span"):
            span.decompose()

    title = css.get_text(title_tag)
    for trash in TITLE_TRASH:
        title = title.replace(trash, "").strip()

    return f"{title} [{playlist_type}]"


def get_playlist_type(url: AbsoluteHttpURL) -> str:
    return next((name for name in PLAYLIST_TITLE_SELECTORS if name in url.parts), "")
