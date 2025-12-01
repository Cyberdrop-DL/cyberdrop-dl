from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, NamedTuple

from cyberdrop_dl.crawlers.crawler import Crawler
from cyberdrop_dl.data_structures.mediaprops import Resolution
from cyberdrop_dl.utils import css, open_graph
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class Selector:
    VIDEO_SRC = ".gif-video, #main_video source"
    COLLECTION_TITLE = "h2.object-title"
    SEARCH_VIDEOS = "div.list-videos div.item > a"
    NEXT_PAGE = "div.pagination-holder li.next > a"


class Format(NamedTuple):
    resolution: Resolution
    link_str: str


class FluidPlayerCrawler(Crawler, is_abc=True):
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    _RATE_LIMIT = 3, 10

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        best_format = _get_best_format(soup)
        link = self.parse_url(best_format.link_str)
        filename, ext = self.get_filename_and_ext(link.name)
        title = open_graph.title(soup)
        scrape_item.possible_datetime = self.parse_iso_date(css.get_json_ld_date(soup))
        custom_filename = self.create_custom_filename(title, ext, file_id=video_id, resolution=best_format.resolution)
        return await self.handle_file(
            scrape_item.url, scrape_item, filename, ext, custom_filename=custom_filename, debrid_link=link
        )

    @error_handling_wrapper
    async def collection(
        self,
        scrape_item: ScrapeItem,
        collection_type: str,
        name: str | None = None,
    ) -> None:
        title: str = ""
        async for soup in self.web_pager(scrape_item.url):
            if not title:
                name = name or css.select_text(soup, Selector.COLLECTION_TITLE)
                title = self.create_title(f"{name} [{collection_type}]")
                scrape_item.setup_as_album(title)

            for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.SEARCH_VIDEOS):
                self.create_task(self.run(new_scrape_item))


def _get_best_format(soup: BeautifulSoup) -> Format:
    parse_resolution = Resolution.make_parser()

    def parse():
        for src in soup.select(Selector.VIDEO_SRC):
            url = css.get_attr(src, "src")
            quality = css.get_attr_or_none(src, "title")
            resolution = parse_resolution(quality)
            yield Format(resolution, url)

    return max(parse())
