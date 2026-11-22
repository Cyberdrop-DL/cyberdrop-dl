from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import json_ld, strict_variadic
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class MasahubCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = (
        "masa49.com",
        "masahub.com",
        "masahub2.com",
        "masafun.net",
        "lol49.com",
        "vido99.com",
    )
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Videos": "/title",
        "Search": "/search/<query>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://lalamasa.mobi")
    DOMAIN: ClassVar[str] = "masahub.com"
    FOLDER_DOMAIN: ClassVar[str] = "Masahub"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("masahub.com",)
    NEXT_PAGE_SELECTOR: ClassVar[str] = "nav > a[href]:-soup-contains('Next')"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["search", query, *_]:
                await self.search(scrape_item, query)
            case [_, *_]:
                await self.video(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        video = json_ld.find_obj(soup, "VideoObject")
        src = self.parse_url(video["contentUrl"])
        _, ext = self.get_filename_and_ext(src.name)
        thumbs = strict_variadic(video["thumbnailUrl"])
        scrape_item.uploaded_at = self.parse_iso_date(video["uploadDate"])
        custom_filename = self.create_custom_filename(video["name"], ext)
        await self.handle_file(
            src,
            scrape_item,
            video["name"],
            ext,
            custom_filename=custom_filename,
            thumbnail=thumbs[0] if thumbs else None,
        )

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        title = self.create_title(query)
        scrape_item.setup_as_album(title)
        found = False
        async for soup in self.web_pager(scrape_item.url):
            for new_item in self.iter_children(scrape_item, soup, "article[data-vid] a"):
                found = True
                self.create_task(self.run(new_item))

        if not found:
            raise ScrapeError.no_content("videos")
