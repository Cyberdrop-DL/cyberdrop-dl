from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, NamedTuple

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.mediaprops import Resolution
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, open_graph
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup, Tag

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class Selector:
    GIF = css.CssAttributeSelector("div.gif-video-wrapper > video", "src")
    VIDEO_SRC = "video#main_video source"
    COLLECTION_TITLE = "h2.object-title"
    SEARCH_VIDEOS = "div.list-videos a.popito"
    NEXT_PAGE = "div.pagination-holder li.next > a"


class Format(NamedTuple):
    resolution: Resolution
    link_str: str


class XGroovyCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/<category>/videos/<video_id>/...",
            "/videos/<video_id>/...",
        ),
        "Gif": (
            "/<category>/gifs/<gif_id>/...",
            "/gifs/<gif_id>/...",
        ),
        "Search": (
            "/<category>/search/...",
            "/search/...",
        ),
        "Pornstar": (
            "/<category>/pornstars/<pornstar_id>/...",
            "/pornstars/<pornstar_id>/...",
        ),
        "Tag": (
            "/<category>/tags/...",
            "/tags/...",
        ),
        "Channel": (
            "/<category>/channels/...",
            "/channels/...",
        ),
    }
    DOMAIN: ClassVar[str] = "xgroovy"
    FOLDER_DOMAIN: ClassVar[str] = "XGroovy"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://xgroovy.com")
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    _RATE_LIMIT = 3, 10

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [*_, "videos", video_id, _]:
                return await self.video(scrape_item, video_id)
            case [*_, "gifs", gif_id, _]:
                return await self.gif(scrape_item, gif_id)
            case [*_, "pornstars" as type_, _]:
                return await self.collection(scrape_item, type_)
            case [*_, "categories" | "channels" | "search" | "tag" as type_, slug]:
                return await self.collection(scrape_item, type_, slug)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def gif(self, scrape_item: ScrapeItem, gif_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        link = self.parse_url(Selector.GIF(soup))
        return await self._video(scrape_item, gif_id, soup, link)

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        best_format = _get_best_format(soup)
        link = self.parse_url(best_format.link_str)
        return await self._video(scrape_item, video_id, soup, link, resolution=best_format.resolution)

    async def _video(
        self,
        scrape_item: ScrapeItem,
        file_id: str,
        soup: BeautifulSoup,
        link: AbsoluteHttpURL,
        resolution: Resolution | None = None,
    ):
        filename, ext = self.get_filename_and_ext(link.name)
        title = open_graph.title(soup)
        scrape_item.possible_datetime = self.parse_iso_date(css.get_json_ld_date(soup))
        custom_filename = self.create_custom_filename(title, ext, file_id=file_id, resolution=resolution)
        return await self.handle_file(link, scrape_item, filename, ext, custom_filename=custom_filename)

    @error_handling_wrapper
    async def collection(self, scrape_item: ScrapeItem, collection_type: str, name: str | None = None) -> None:
        title: str = ""
        async for soup in self.web_pager(scrape_item.url):
            if not title:
                name = name or css.select_one_get_text(soup, Selector.COLLECTION_TITLE)
                title = self.create_title(f"{name} [{collection_type}]")
                scrape_item.setup_as_album(title)

            for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.SEARCH_VIDEOS):
                self.create_task(self.run(new_scrape_item))


def _get_best_format(soup: Tag) -> Format:
    def parse():
        for src in soup.select(Selector.VIDEO_SRC):
            url = css.get_attr(src, "src")
            if title := css.get_attr_or_none(src, "title"):
                resolution = Resolution.parse(title)
            else:
                resolution = Resolution.unknown()
            yield Format(resolution, url)

    return max(parse())
