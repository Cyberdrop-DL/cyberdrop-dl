from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, final, override

from cyberdrop_dl import aio, signature
from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers._kvs import extract_kvs_video
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths, URLConfig
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, json_ld
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.urls import URLDeduper

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.mediaprops import Resolution
    from cyberdrop_dl.url_objects import ScrapeItem


_PER_PAGE: int = 1000


@dataclasses.dataclass(slots=True)
class KVSVideo:
    id: str
    title: str
    url: AbsoluteHttpURL
    resolution: Resolution


@final
class Selector:
    MODEL_NAME = "[class^='blocks-model-view-title'] h1"
    ITEM = "a[class^='ui-card-link_']"
    ALBUM_TAB = "[class^='pages-view-model-heading'] a[href*='/albums/onlyfans-creators/']"
    ALBUM_TITLE = "#album_view_album_view h1"
    NOT_FOUND = "main[class^='pages-404-wrapper']"
    NEXT_PAGE = "li a[class^='includes-pagination-arrow']"


def _pagination_query(url: AbsoluteHttpURL) -> dict[str, Any]:
    return {
        "albums_per_page" if "albums" in url.parts else "videos_per_page": _PER_PAGE,
        "sort_by": url.query.get("sort_by", "post_date"),
    }


@URLConfig(trim=False)
@HTTPConfig(impersonate=True)
class PimpBunnyCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Videos": "/videos/...",
        "Models": "/onlyfans-creators/<model_name>",
        "Model Albums": "/albums/models/<model_name>",
        "Album": "/albums/<album_name>",
        "Category": "/categories/<category>",
        "Tag": "/tags/<tag>",
    }

    DOMAIN: ClassVar[str] = "pimpbunny.com"
    FOLDER_DOMAIN: ClassVar[str] = "PimpBunny"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pimpbunny.com")

    def __post_init__(self) -> None:
        self.update_cookies({"is_age_ok": 1, "kt_tcookie": 1, "kt_is_visited": 1})

    async def _pager(self, url: AbsoluteHttpURL) -> AsyncIterator[BeautifulSoup]:
        pages = URLDeduper()
        while True:
            if url in pages:
                break
            soup = await self.request_soup(url)
            yield soup
            arrows = soup.select(Selector.NEXT_PAGE)
            assert len(arrows) in {0, 1, 2}
            if not arrows:
                break
            url = self.parse_url(css.attr(arrows[-1], "href"))

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["videos", _, *_]:
                await self.video(scrape_item)
            case ["onlyfans-creators", model_name, *_]:
                await self.model(scrape_item, model_name)
            case ["albums", "models", model_name, *_]:
                await self.model_albums(scrape_item, model_name)
            case ["albums", name, *_]:
                await self.album(scrape_item, name)
            case ["categories" as type_, name, *_]:
                await self.collection(scrape_item, type_, name)
            case ["tags" as type_, name, *_]:
                await self.collection(scrape_item, type_, name)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def collection(self, scrape_item: ScrapeItem, collection_type: str, slug: str) -> None:
        url = scrape_item.url.origin() / collection_type / slug / ""
        title = self.create_title(f"{slug} [{collection_type}]")
        scrape_item.setup_as_album(title)

        query = _pagination_query(scrape_item.url)
        async for soup in self._pager(url.with_query(query)):
            for new_scrape_item in self.iter_children(scrape_item, soup, Selector.ITEM):
                self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def model(self, scrape_item: ScrapeItem, model_name: str) -> None:
        model_url = scrape_item.url.origin() / "onlyfans-models" / model_name / ""
        has_albums: bool = False
        soup, pages = await aio.peek_next(self._pager(model_url.with_query(_pagination_query(scrape_item.url))))
        name = css.select_text(soup, Selector.MODEL_NAME)
        scrape_item.setup_as_profile(self.create_title(f"{name} [model]"))

        async for soup in pages:
            for new_item in self.iter_children(scrape_item, soup, Selector.ITEM):
                self.create_task(self.run(new_item))

            if not has_albums:
                has_albums = bool(soup.select_one(Selector.ALBUM_TAB))

        if has_albums:
            await self.model_albums(scrape_item, model_name)

    @override
    @signature.copy(Crawler.request_soup)
    async def request_soup(self, *args, **kwargs) -> BeautifulSoup:
        soup = await super().request_soup(*args, **kwargs)
        if soup.select_one(Selector.NOT_FOUND):
            raise ScrapeError(404) from None
        return soup

    @error_handling_wrapper
    async def model_albums(self, scrape_item: ScrapeItem, model_name: str) -> None:
        albums_url = scrape_item.url.origin() / "albums/models" / model_name / ""
        name: str = ""

        query = _pagination_query(scrape_item.url)
        async for soup in self._pager(albums_url.with_query(query)):
            if not name:
                name = css.select_text(soup, Selector.MODEL_NAME)
                scrape_item.setup_as_profile(self.create_title(f"{name} [model]"))

            for new_scrape_item in self.iter_children(scrape_item, soup, Selector.ITEM):
                self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        video = extract_kvs_video(self, soup)

        custom_filename = self.create_custom_filename(
            video.title, video.url.suffix or video.url.parent.suffix, file_id=video.id, resolution=video.resolution
        )

        scrape_item.uploaded_at = json_ld.upload_date(soup)
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            video.url.name,
            video.url.suffix,
            custom_filename=custom_filename,
            debrid_link=video.url,
        )

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, name: str) -> None:
        album_url = scrape_item.url.origin() / "albums" / name / ""
        soup, pages = await aio.peek_next(self._pager(album_url))
        title = css.select_text(soup, Selector.ALBUM_TITLE)
        scrape_item.setup_as_album(self.create_title(f"{title} [album]"))

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            async for soup in pages:
                for image in self.iter_urls(soup, Selector.ITEM):
                    tg.create_task(self.direct_file(scrape_item, image))
                    scrape_item.add_children()
                    await sleep()
