from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.twitter_images import TwimgCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedDomains
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    NEXT_PAGE = "li > a:-soup-contains('»')"

    TITLE = "h1.user-page, h1.tag-page, h1.block__title"
    THUMBS = "div.block-thumbs a.thumb__link"
    _VIDEO = "video.video-js > source"
    _PHOTO = "img.thumb__img"
    MEDIA = f"{_VIDEO}, {_PHOTO}"


class TwPornstarsCrawler(TwimgCrawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = (
        "www.twgays.com",
        "www.twmilf.com",
        "www.twlesbian.com",
        "www.twteens.com",
        "www.twonfans.com",
        "www.twtiktoks.com",
        "www.twgaymuscle.com",
        "www.twanal.com",
        "www.indiantw.com",
        "www.twpornstars.com",
    )
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.twpornstars.com")
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    DOMAIN: ClassVar[str] = "twpornstars"
    FOLDER_DOMAIN: ClassVar[str] = "TWPornStars"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["p", _post_id]:
                return await self.media(scrape_item)
            case [_]:
                return await self.collection(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def media(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        src = self.parse_url(css.select(soup, Selector.MEDIA, "src"))
        src = src.with_path(src.path.removesuffix(":large"))
        if "video" in src.host:
            await self.direct_file(scrape_item, src)
            return
        await self.photo(scrape_item, src)

    @error_handling_wrapper
    async def collection(self, scrape_item: ScrapeItem) -> None:
        title: str = ""
        async for soup in self.web_pager(scrape_item.url):
            if not title:
                name = css.select_text(soup, Selector.TITLE)
                title = self.create_title(name.removesuffix("'s pics and videos"))
                scrape_item.setup_as_album(title)

            for _, new_item in self.iter_children(scrape_item, soup, Selector.THUMBS):
                self.create_task(self.run(new_item))
