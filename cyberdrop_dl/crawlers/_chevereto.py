from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING, Any, ClassVar, final

from cyberdrop_dl.crawlers.crawler import Crawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import PasswordProtectedError
from cyberdrop_dl.utils import css, json, open_graph
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL, ScrapeItem


class Selector:
    ITEM_DESCRIPTION = "p[class*=description-meta]"
    ITEM = "a.image-container"
    NEXT_PAGE = "a[data-pagination=next]"

    DATE_SINGLE_ITEM = f"{ITEM_DESCRIPTION}:-soup-contains('Uploaded') span"
    DATE_ALBUM_ITEM = f"{ITEM_DESCRIPTION}:-soup-contains('Added to') span"
    DATE = css.CssAttributeSelector(f"{DATE_SINGLE_ITEM}, {DATE_ALBUM_ITEM}", "title")
    MAIN_IMAGE = css.CssAttributeSelector("div#image-viewer img", "src")


class CheveretoCrawler(Crawler, is_generic=True):
    SUPPORTED_PATHS: ClassVar[dict[str, str | tuple[str, ...]]] = {
        "Album": (
            "/a/<id>",
            "/a/<name>.<id>",
            "/album/<id>",
            "/album/<name>.<id>",
        ),
        "Category": "/category/<name>",
        "Image": (
            "/img/<id>",
            "/img/<name>.<id>",
            "/image/<id>",
            "/image/<name>.<id>",
        ),
        "Profile": "/<user_name>",
        "Video": (
            "/video/<id>",
            "/video/<name>.<id>",
            "/videos/<id>",
            "/videos/<name>.<id>",
        ),
        "Direct links": "",
    }
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    DEFAULT_TRIM_URLS: ClassVar[bool] = False
    CHEVERETO_SUPPORTS_VIDEO: ClassVar[bool] = True

    def __init_subclass__(cls, **kwargs: Any) -> None:
        if not cls.CHEVERETO_SUPPORTS_VIDEO:
            cls.SUPPORTED_PATHS = paths = cls.SUPPORTED_PATHS.copy()  # type: ignore[reportIncompatibleVariableOverride]  # pyright: ignore[reportConstantRedefinition]
            _ = paths.pop("Video", None)
        super().__init_subclass__(**kwargs)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if self.is_subdomain(scrape_item.url):
            return await self.direct_file(scrape_item)

        match scrape_item.url.parts[1:]:
            case ["a" | "album" | "category", album_slug]:
                return await self.album(scrape_item, _id(album_slug))
            case ["img" | "image" | "video" | "videos", _]:
                return await self.media(scrape_item)
            case ["images", _, *_]:
                return await self.direct_file(scrape_item)
            case [_, "albums"]:
                return await self.profile(scrape_item, albums=True)
            case [_]:
                return await self.profile(scrape_item)
            case _:
                raise ValueError

    @final
    @staticmethod
    def _thumbnail_to_src(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        new_name = url.name
        for trash in (".md.", ".th.", ".fr."):
            new_name = new_name.replace(trash, ".")
        return url.with_name(new_name)

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["a" | "album" as part, album_slug, "sub"]:
                return url.with_path(f"{part}/{album_slug}", keep_query=True)
            case ["img" | "image" | "video" | "videos" as part, slug]:
                return url.with_path(f"{part}/{_id(slug)}", keep_query=True)
            case _:
                return url

    async def _get_final_album_url(self, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        if "category" in url.parts:
            return url

        # We need the full URL (aka "/<name>.<id>") to fetch sub albums
        while "." not in (url.name or url.parent.name):
            url = await self._get_redirect_url(url)

        return url

    async def web_pager(
        self, url: AbsoluteHttpURL, next_page_selector: str | None = None, *, cffi: bool = False, **kwargs: Any
    ) -> AsyncGenerator[BeautifulSoup]:
        async for soup in super().web_pager(_sort_by_new(url), next_page_selector, cffi=cffi, trim=False, **kwargs):
            yield soup

    @error_handling_wrapper
    async def profile(self, scrape_item: ScrapeItem, *, albums: bool = False) -> None:
        title: str = ""
        async for soup in self.web_pager(scrape_item.url):
            if not title:
                title = self.create_title(open_graph.title(soup))
                scrape_item.setup_as_profile(title)

            if albums:
                for _, sub_album in self.iter_children(scrape_item, soup, Selector.ITEM):
                    self.create_task(self.run(sub_album))

                return

            self._iter_album_files(scrape_item, soup)

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        results: dict[str, int] = {}
        title: str = ""

        scrape_item.url = await self._get_final_album_url(scrape_item.url)

        async for soup in self.web_pager(scrape_item.url):
            if not title:
                if soup.select_one("form"):
                    await self._unlock_pw_protected_album(scrape_item, soup)
                    return await self.album(scrape_item, album_id)

                results = await self.get_album_results(album_id)
                title = open_graph.get_title(soup) or open_graph.description(soup)
                title = self.create_title(title, album_id)
                scrape_item.setup_as_album(title, album_id=album_id)

            self._iter_album_files(scrape_item, soup, results)

        async for soup in self.web_pager(scrape_item.url / "sub"):
            for _, sub_album in self.iter_children(scrape_item, soup, Selector.ITEM):
                self.create_task(self.run(sub_album))

    def _iter_album_files(
        self, scrape_item: ScrapeItem, soup: BeautifulSoup, results: dict[str, int] | None = None
    ) -> None:
        results = results or {}
        for web_url, src_url in self._get_album_files(soup):
            if self.check_album_results(web_url, results):
                continue

            new_scrape_item = scrape_item.create_child(web_url)
            self.create_task(self.direct_file(new_scrape_item, src_url))
            scrape_item.add_children()

    async def _unlock_pw_protected_album(self, scrape_item: ScrapeItem, soup: BeautifulSoup) -> None:
        if not scrape_item.password:
            raise PasswordProtectedError

        soup = await self.request_soup(
            _sort_by_new(scrape_item.url / ""),
            method="POST",
            data={
                "auth_token": css.select(soup, "[name=auth_token]", "value"),
                "content-password": scrape_item.password,
            },
        )

        if soup.select_one("form"):
            raise PasswordProtectedError(message="Wrong password")

    @error_handling_wrapper
    async def direct_file(
        self, scrape_item: ScrapeItem, url: AbsoluteHttpURL | None = None, assume_ext: str | None = None
    ) -> None:
        link = self._thumbnail_to_src(url or scrape_item.url)
        await super().direct_file(scrape_item, link, assume_ext)

    @error_handling_wrapper
    async def media(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        link_str = open_graph.get_video(soup) or open_graph.get_image(soup)
        if not link_str or "loading.svg" in link_str:
            link_str = Selector.MAIN_IMAGE(soup)

        source = self.parse_url(link_str)
        scrape_item.possible_datetime = self.parse_iso_date(Selector.DATE(soup))
        await self.direct_file(scrape_item, source)

    def _get_album_files(self, soup: BeautifulSoup) -> Generator[tuple[AbsoluteHttpURL, AbsoluteHttpURL]]:
        for item in soup.select(".list-item[data-object]"):
            web_url = self.parse_url(css.select(item, "a.image-container", "href"))
            encoded_data = css.get_attr(item, "data-object")
            data = json.loads(urllib.parse.unquote(encoded_data))
            src_url = self.parse_url(data["image"]["url"])
            yield self.transform_url(web_url), src_url


def _id(slug: str) -> str:
    return slug.rsplit(".")[-1]


def _sort_by_new(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    init_page = int(url.query.get("page") or 1)
    if url.name:
        url = url / ""
    return url.with_query(sort="date_desc", page=init_page)
