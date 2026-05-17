from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    CONTENT = "div[id=content] a"
    IMAGES = ".main_content .uk-align-center img"
    NEXT_PAGE = 'div[id="next_page"] a'


class FapelloComCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Individual Post": "/<model_nam>/<post_id>",
        "Model": "/<name>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://fapello.com")
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    DOMAIN: ClassVar[str] = "fapello.com"
    _RATE_LIMIT: ClassVar[RateLimit] = 5, 1

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_]:
                return await self.model(scrape_item)
            case [model, post_id]:
                return await self.post(scrape_item, model, int(post_id))
            case _:
                raise ValueError

    @error_handling_wrapper
    async def model(self, scrape_item: ScrapeItem) -> None:
        async for soup in self.web_pager(scrape_item.url):
            for post in soup.select(Selector.CONTENT):
                link_str: str = css.attr(post, "href")
                if "javascript" in link_str:
                    link_str = css.select(post, "iframe", "src")

                link = self.parse_url(link_str)
                new_scrape_item = scrape_item.create_child(link)
                self.handle_external_links(new_scrape_item)
                scrape_item.add_children()

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, model: str, post_id: int) -> None:
        scrape_item.setup_as_album(self.create_title(model))
        soup = await self.request_soup(scrape_item.url)
        for _, link in self.iter_tags(soup, Selector.IMAGES, "src"):
            self.create_task(self.direct_file(scrape_item, link))
            scrape_item.add_children()
