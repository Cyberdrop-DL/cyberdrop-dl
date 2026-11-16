from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, ClassVar, final, override

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths, URLConfig
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


@final
class Selector:
    MODEL_NAME = "#content header h1"
    PAGE_TITLE = "header h1"
    GALLERY = "ul.list-gallery"
    GALLERY_IMAGES = "li > a"
    PAGE_ITEMS = "li > figure > a"
    NEXT_PAGE = "nav.nav-pagination a[rel=next]"


@URLConfig(trim=False)
class ElitebabesCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Gallery": "/<slug>",
        "Channel": (
            "/<name>",
            "/<name>/s/popular",
            "/<name>/s/newest",
        ),
        "Model": "/model/<name>/...",
        "Direct File": "",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.elitebabes.com")
    DOMAIN: ClassVar[str] = "elitebabes"
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE

    @override
    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if self.is_subdomain(scrape_item.url):
            await self.direct_file(scrape_item)
            return

        match scrape_item.url.parts[1:]:
            case ["model", _name, *_]:
                await self.page(scrape_item)
            case [slug] | [slug, ""] | [slug, "s", _] if slug not in {
                "tag",
                "sort",
                "pinboards",
                "erotic-art-channels",
                "collections",
                "community",
            }:
                await self.page(scrape_item)
            case _:
                raise ValueError

    async def _grid_api_galleries(self, url: AbsoluteHttpURL, *, init_page: int = 1) -> AsyncGenerator[BeautifulSoup]:
        for page in itertools.count(init_page):
            html = await self.request_html(url.update_query(mpage=page))
            if html.startswith("no more "):
                break
            yield await css.asoup(html)

    @error_handling_wrapper
    async def page(self, scrape_item: ScrapeItem) -> None:
        async with self.request(scrape_item.url) as resp:
            html = await resp.html()
            soup = await resp.soup()
            galleries = aio.to_async_iterable([css.select(soup, Selector.GALLERY)])

        try:
            name = css.select_text(soup, Selector.MODEL_NAME)
        except css.SelectorError:
            name = css.select_text(soup, Selector.PAGE_TITLE)

        if api_url := extr_text(html, "const apiUrl = '", "'"):
            url = self.parse_url(api_url)
            kind = url.query["content"].removesuffix("_old")
            assert kind
            name = f"{name} [{kind}]"
            galleries = aio.chain(galleries, self._grid_api_galleries(url, init_page=2))
            selector = Selector.PAGE_ITEMS
        else:
            selector = Selector.GALLERY_IMAGES

        scrape_item.setup_as_album(self.create_title(name))
        sleep = aio.periodic_sleep(10)
        async for gallery in galleries:
            for url in self.iter_urls(gallery, selector, "href"):
                self.handle_embed(scrape_item.create_child(url))
                scrape_item.add_children()
                await sleep()
