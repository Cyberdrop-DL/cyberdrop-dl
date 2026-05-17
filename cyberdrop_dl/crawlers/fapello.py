from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    POSTS = "a[href]:has(img)"
    IMAGE_OR_VIDEO = ".main_content .uk-align-center [src]"
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
            case [model]:
                return await self.model(scrape_item, model)
            case [model, post_id]:
                return await self.post(scrape_item, model, int(post_id))
            case _:
                raise ValueError

    @error_handling_wrapper
    async def model(self, scrape_item: ScrapeItem, model: str) -> None:
        api_url = self.PRIMARY_URL / "ajax/model" / model
        for page in itertools.count(1):
            soup = await self.request_soup(api_url / f"page-{page}")
            posts = tuple(css.iselect(soup, Selector.POSTS, "href"))
            for post in posts:
                new_scrape_item = scrape_item.create_child(self.parse_url(post))
                self.create_task(self.run(new_scrape_item))
                scrape_item.add_children()

            if len(posts) < 32:
                break

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, model: str, post_id: int) -> None:
        scrape_item.setup_as_album(self.create_title(model))
        soup = await self.request_soup(scrape_item.url)
        for _, link in self.iter_tags(soup, Selector.IMAGE_OR_VIDEO, "src"):
            self.create_task(self.direct_file(scrape_item, link))
            scrape_item.add_children()
