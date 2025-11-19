from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class Selector:
    VIDEO_SRC = css.CssAttributeSelector("#placeVideo #videoContainer", "data-high")
    VIDEO_TITLE = "span.movie-title-text"
    ITEM_THUMBS = "div.thumbs-container a.pp"

    MODEL_NAME = "h1.ps-heading-name"
    ALBUM_TITLE = "h1.top"
    IMAGES = "div.pic-list a"


MAX_VIDEO_COUNT_PER_PAGE = 52


class TrannyOneCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/view/<video_id>",
        "Search": "/search/<search_query>",
        "Pornstars": "/pornstar/<model_id>/<model_name>",
        "Album": "/pics/album/<album_id>",
    }
    DOMAIN: ClassVar[str] = "tranny.one"
    FOLDER_DOMAIN: ClassVar[str] = "Tranny.One"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.tranny.one")
    _RATE_LIMIT = 3, 10

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if self.is_subdomain(scrape_item.url):
            return await self.direct_file(scrape_item)

        match scrape_item.url.parts[1:]:
            case ["view", video_id]:
                return await self.video(scrape_item, video_id)
            case ["search", query]:
                return await self.search(scrape_item, query)
            case ["pornstars", model_id, _]:
                return await self.model(scrape_item, model_id)
            case ["pics", "album", album_id]:
                return await self.album(scrape_item, album_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        title = css.select_one_get_text(soup, Selector.VIDEO_TITLE)
        link = self.parse_url(Selector.VIDEO_SRC(soup))
        filename, ext = self.get_filename_and_ext(link.name)
        custom_filename = self.create_custom_filename(title, ext, file_id=video_id)
        return await self.handle_file(link, scrape_item, filename, ext, custom_filename=custom_filename)

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        title = self.create_title(f"{query} [search]]")
        scrape_item.setup_as_album(title)
        await self._iter_videos(scrape_item)

    async def _iter_videos(self, scrape_item: ScrapeItem) -> None:
        for page in itertools.count(1):
            page_url = scrape_item.url.with_query(pageId=page)
            soup = await self.request_soup(page_url)
            n_videos = 0
            for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.ITEM_THUMBS):
                n_videos += 1
                self.create_task(self.run(new_scrape_item))

            if n_videos < MAX_VIDEO_COUNT_PER_PAGE:
                break

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        name = css.select_one_get_text(soup, Selector.ALBUM_TITLE)
        scrape_item.setup_as_album(self.create_title(f"{name} [album]"), album_id=album_id)
        results = await self.get_album_results(album_id)
        for _, pic in self.iter_tags(soup, Selector.IMAGES, results=results):
            self.create_task(self.direct_file(scrape_item, pic))

    @error_handling_wrapper
    async def model(self, scrape_item: ScrapeItem, model_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        name = css.select_one_get_text(soup, Selector.MODEL_NAME)
        scrape_item.setup_as_profile(self.create_title(f"{name} [model]"))

        ajax_url = self.PRIMARY_URL.with_query(area="pornstarsViewer", ajax=1, id=model_id, tab="albums")
        soup = await self.request_soup(ajax_url)
        for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.ITEM_THUMBS):
            self.create_task(self.run(new_scrape_item))

        await self._iter_videos(scrape_item)
