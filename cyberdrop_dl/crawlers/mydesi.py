from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, json, strict_variadic
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.urls import parse_http_url

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class MyDesiCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Videos": "/<slug>",
        "Search": "/search/<query>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://p4455.com")
    DOMAIN: ClassVar[str] = "mydesi.net"
    FOLDER_DOMAIN: ClassVar[str] = "MyDesi"
    OLD_DOMAINS: ClassVar[SupportedDomains] = "fry99.com", "lolpol.com", "mydesi.net"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["search", query, *rest]:
                match rest:
                    case ["page", init_page]:
                        init_page = int(init_page)
                    case _:
                        init_page = 1
                await self.search(scrape_item, query, init_page)
            case [_]:
                await self.video(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        html = await self.request_html(scrape_item.url)
        src, title = await _extr_video(html)
        _, ext = self.get_filename_and_ext(src.name)
        await self.handle_file(src, scrape_item, title, ext, custom_filename=self.create_custom_filename(title, ext))

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str, init_page: int = 1) -> None:
        title = self.create_title(f"{query} [search]")
        scrape_item.setup_as_album(title)

        base_url = scrape_item.url.origin() / "search" / query / "page"
        sleep = aio.periodic_sleep(10)
        for page in itertools.count(init_page):
            soup = await self.request_soup(base_url / str(page))
            n_videos = 0
            for new_item in self.iter_children(scrape_item, soup, ".grid .card[data-md] a.thumb"):
                n_videos += 1
                self.create_task(self.run(new_item, check_referer=True))
                await sleep()

            if n_videos < 38:
                break


@aio.to_thread
def _extr_video(html: str) -> tuple[AbsoluteHttpURL, str]:
    soup = css.soup(html)
    sources = {s["label"]: s["src"] for s in strict_variadic(json.loads(css.select(soup, "#player", "data-sources")))}
    src = parse_http_url(sources.get("HD") or sources["SD"])
    return src, css.select_text(soup, ".panel h1")
