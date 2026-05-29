from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths, auto_task_id
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper, open_graph

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    ALBUM = 'a[href^="/album/"]'
    ALBUM_NAME = ".panel-heading > .pull-left"

    IMAGE = "img.img-responsive-mw"
    THUMBNAIL = "img[id^='album_photo_']"

    VIDEO = "a[href^='/video/']"
    VIDEO_SRC = "source[title='HD'], source[title='SD']"


class TokioMotionCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Albums": (
            "/user/<user>/albums/",
            "/album/<album_id>",
        ),
        "Photo": (
            "/photo/<photo_id>",
            "/user/<user>/favorite/photos",
        ),
        "Playlist": "/user/<user>/favorite/videos",
        "Profiles": "/user/<user>",
        "Search Results": "/search?...",
        "Video": "/video/<video_id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.tokyomotion.net")
    NEXT_PAGE_SELECTOR: ClassVar[str] = "a.prevnext"
    DOMAIN: ClassVar[str] = "tokyomotion"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        scrape_item.url = scrape_item.url.without_query_params("page")

        match scrape_item.url.parts[1:]:
            case ["video", video_id, *_]:
                return await self.video(scrape_item, video_id)
            case ["photo", _]:
                return await self.photo(scrape_item)
            case ["album", album_id, *_]:
                return await self.album(scrape_item, album_id)
            case ["user", user, *_]:
                title = self.create_title(f"{user} [user]")
                scrape_item.setup_as_profile(title)
                return await self.profile(scrape_item)
            case ["search"] if (
                (query := scrape_item.url.query.get("search_query"))
                and (query_type := scrape_item.url.query.get("search_type"))
                and query_type != "users"
            ):
                return await self.search(scrape_item, query, query_type)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        scrape_item.url = scrape_item.url.with_path(f"video/{video_id}")
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        _check_private(soup)
        src = css.select(soup, Selector.VIDEO_SRC, "src")
        link = self.parse_url(src)
        title = open_graph.title(soup)
        filename = self.create_custom_filename(title, ext := ".mp4", file_id=video_id)
        await self.handle_file(link, scrape_item, video_id + ext, ext, custom_filename=filename)

    @error_handling_wrapper
    async def photo(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        _check_private(soup)
        src = css.select(soup, Selector.IMAGE, "src")
        await self.direct_file(scrape_item, self.parse_url(src))

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        _check_private(soup)
        title = css.select_text(soup, Selector.ALBUM_NAME)
        scrape_item.setup_as_album(self.create_title(title, album_id), album_id=album_id)

        while True:
            self._iter_album_images(scrape_item, soup)
            try:
                next_page = css.select(soup, self.NEXT_PAGE_SELECTOR, "href")
            except css.SelectorError:
                break
            soup = await self.request_soup(self.parse_url(next_page))

    def _iter_album_images(self, scrape_item: ScrapeItem, soup: BeautifulSoup) -> None:
        for link in css.iselect(soup, Selector.THUMBNAIL, "src"):
            src = self.parse_url(link.replace("/tmb/", "/"))
            self.create_task(self.direct_file(scrape_item, src))

    @error_handling_wrapper
    async def profile(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[3:]:
            case ["favorite", "videos"]:
                scrape_item.setup_as_album("favorite")
                scrape_item.append_folder("videos")
                return await self.crawl_children(scrape_item, Selector.VIDEO)

            case ["videos"]:
                scrape_item.setup_as_album("videos")
                return await self.crawl_children(scrape_item, Selector.VIDEO)

            case ["favorite", "photos"]:
                scrape_item.setup_as_album("favorite")
                scrape_item.append_folder("photos")
                async for soup in self._web_pager(scrape_item.url):
                    self._iter_album_images(scrape_item, soup)

            case ["photos"]:
                scrape_item.setup_as_album("photos")
                async for soup in self._web_pager(scrape_item.url):
                    self._iter_album_images(scrape_item, soup)

            case ["albums"]:
                scrape_item.setup_as_album("albums")
                return await self.crawl_children(scrape_item, Selector.ALBUM)

            case []:
                for path in ("albums", "favorite/photos", "videos", "favorite/videos"):
                    new_item = scrape_item.create_child(scrape_item.url / path)
                    self.create_task(self._profile_page(new_item))
                    scrape_item.add_children()
            case _:
                raise ScrapeError("Unknown URL path")

    _profile_page = auto_task_id(profile)

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str, query_type: str) -> None:
        title = f"{query} [{query_type} search]"
        scrape_item.setup_as_album(self.create_title(title))
        selector = Selector.ALBUM if query_type == "photos" else Selector.VIDEO
        return await self.crawl_children(scrape_item, selector)

    @error_handling_wrapper
    async def crawl_children(self, scrape_item: ScrapeItem, selector: str) -> None:
        async for soup in self._web_pager(scrape_item.url):
            for _, new_item in self.iter_children(scrape_item, soup, selector):
                self.create_task(self.run(new_item))

    async def _web_pager(self, url: AbsoluteHttpURL) -> AsyncIterator[BeautifulSoup]:
        is_fist_page: bool = True
        async for soup in self.web_pager(url):
            if is_fist_page:
                _check_private(soup)
                is_fist_page = False
            yield soup


def _check_private(soup: BeautifulSoup) -> None:
    if "This is a private" in soup.get_text():
        raise ScrapeError(401, "Private - Requires being friends with the owner")
