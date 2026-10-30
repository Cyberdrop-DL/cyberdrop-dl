from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, ClassVar, Unpack, override

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, open_graph
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.clients.request import RequestParams
    from cyberdrop_dl.clients.response import AbstractResponse
    from cyberdrop_dl.constants import HttpMethod
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    ALBUM = "a.album-link"
    MEDIA = ".media-group " + css.where("img.img-front", ".video video > source")
    THUMB = "video[poster]"
    NEXT_PAGE = 'a[rel="next"]'


class EromeCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/a/<album_id>",
        "Profile": "/<name>",
        "Search": "/search?q=<query>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.erome.com")
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    DOMAIN: ClassVar[str] = "erome"
    csrf_token: str = ""

    async def __async_post_init__(self) -> None:
        self.csrf_token_lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        if url.host == "erome.com":
            return url.with_host("www.erome.com")
        return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["a", album_id, *_]:
                await self.album(scrape_item, album_id)
            case ["search", *_] if query := scrape_item.url.query.get("q"):
                await self.search(scrape_item, query)
            case [name]:
                await self.profile(scrape_item, name)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def profile(self, scrape_item: ScrapeItem, name: str) -> None:
        title = self.create_title(name)
        scrape_item.setup_as_profile(title)

        async for soup in self.web_pager(scrape_item.url):
            for new_item in self.iter_children(scrape_item, soup, Selector.ALBUM):
                self.create_task(self.run(new_item))

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        title = self.create_title(f"{query} [search]")
        scrape_item.setup_as_album(title)
        async for soup in self.web_pager(scrape_item.url):
            for new_item in self.iter_children(scrape_item, soup, Selector.ALBUM):
                self.create_task(self.run(new_item))

    @override
    @contextlib.asynccontextmanager
    async def request(
        self, url: AbsoluteHttpURL, /, method: HttpMethod = "GET", **kwargs: Unpack[RequestParams]
    ) -> AsyncGenerator[AbstractResponse]:

        async with super().request(url, method, **kwargs) as resp:
            if self.csrf_token:
                yield resp
                return

            async with self.csrf_token_lock:
                if not self.csrf_token:
                    token = css.select(await resp.soup(parse_only="meta"), "meta[name='csrf-token']", "content")
                    async with super().request(
                        url.origin() / "user/disclaimer",
                        "POST",
                        headers={
                            "X-CSRF-TOKEN": token,
                            "Referer": str(url),
                            "X-Requested-With": "XMLHttpRequest",
                        },
                    ):
                        ...
                    self.csrf_token = token

            yield resp

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        async with self.request(scrape_item.url) as resp:
            soup = await resp.soup()
            scrape_item.url = resp.url

        name = open_graph.title(soup).removesuffix("- EroMe")
        title = self.create_title(name, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        downloaded = await self.get_completed_by_album(album_id)
        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            for media in self.iter_urls(soup, Selector.MEDIA, "src"):
                if media in downloaded:
                    continue

                try:
                    thumb = css.select(soup, "video[poster]", "poster")
                except css.SelectorError:
                    thumb = None

                tg.create_task(self._file(scrape_item, media, thumb))
                scrape_item.add_children()
                await sleep()

    async def _file(
        self, scrape_item: ScrapeItem, /, url: AbsoluteHttpURL, thumb: AbsoluteHttpURL | str | None = None
    ) -> None:
        async with self.catch_errors(url):
            name = url.name or url.parent.name
            filename, ext = self.get_filename_and_ext(name)
            await self.handle_file(url, scrape_item, name, ext, thumbnail=thumb, custom_filename=filename)


class EromeFanCrawler(EromeCrawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = ("erome.fan",)
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/a/<album_id>",
        "Profile": "/a/category/<name>",
        "Search": "/search/<query>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://erome.fan")
    DOMAIN: ClassVar[str] = "erome.fan"
    FOLDER_DOMAIN: ClassVar[str] = "Erome.fan"
    NEXT_PAGE_SELECTOR: ClassVar[str] = "a.next"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["a", "category", name, *_]:
                await self.profile(scrape_item, name)
            case ["a", album_id, *_]:
                await self.album(scrape_item, album_id)
            case ["search", query, *_]:
                await self.search(scrape_item, query)
            case _:
                raise ValueError
