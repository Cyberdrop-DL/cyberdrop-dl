from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    CONTENT = "div[class=items] div a"
    MEDIA = "img#image, video source"


class RealBooruCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File": "?id=<file_id>",
        "Tags": "?tags=<name>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://realbooru.com")
    NEXT_PAGE_SELECTOR: ClassVar[str] = "a[alt=next]"
    DOMAIN: ClassVar[str] = "realbooru"
    FOLDER_DOMAIN: ClassVar[str] = "RealBooru"

    def __post_init__(self) -> None:
        self.update_cookies({"resize-original": "1"})

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["index.php"]:
                query = scrape_item.url.query
                if tags := query.get("tags"):
                    return await self.tags(scrape_item, tags)
                if query.get("id"):
                    return await self.file(scrape_item)
                raise ValueError
            case _:
                raise ValueError

    @error_handling_wrapper
    async def tags(self, scrape_item: ScrapeItem, tags: str) -> None:
        scrape_item.setup_as_album(self.create_title(tags.strip()))
        async for soup in self.web_pager(scrape_item.url, relative_to=scrape_item.url):
            for new_item in self.iter_children(scrape_item, soup, Selector.CONTENT):
                self.create_task(self.run(new_item))

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)
        src = css.select(soup, Selector.MEDIA, "src")
        await self.direct_file(scrape_item, self.parse_url(src))
