from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper, extr_text

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    CONTENT = "div[class=image-list] span a"
    DATE = "li:-soup-contains('Posted: ')"
    _IMAGE = "img[id=image]"
    _VIDEO = "video source"
    IMAGE_OR_VIDEO = f"{_IMAGE}, {_VIDEO}"


class Rule34XXXCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File": "?id=...",
        "Tag": "?tags=...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://rule34.xxx")
    NEXT_PAGE_SELECTOR: ClassVar[str] = "a[alt=next]"
    DOMAIN: ClassVar[str] = "rule34.xxx"
    FOLDER_DOMAIN: ClassVar[str] = "Rule34XXX"

    async def __async_post_init__(self) -> None:
        self.update_cookies({"resize-original": "1"})

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if tags := scrape_item.url.query.get("tags"):
            return await self.tag(scrape_item, tags)
        if scrape_item.url.query.get("id"):
            return await self.file(scrape_item)
        raise ValueError

    @error_handling_wrapper
    async def tag(self, scrape_item: ScrapeItem, tags: str) -> None:
        title: str = ""
        async for soup in self.web_pager(scrape_item.url, relative_to=scrape_item.url):
            if not title:
                title = self.create_title(tags.strip())
                scrape_item.setup_as_album(title)

            for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.CONTENT):
                self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)
        date = extr_text(css.select_text(soup, Selector.DATE), "Posted: ", "by")
        scrape_item.uploaded_at = self.parse_iso_date(date)
        link_str = css.select(soup, Selector.IMAGE_OR_VIDEO, "src")
        await self.direct_file(scrape_item, self.parse_url(link_str))
