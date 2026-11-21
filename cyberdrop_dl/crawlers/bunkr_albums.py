from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Unpack, final, override

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths, URLConfig
from cyberdrop_dl.exceptions import DDOSGuardError, DownloadError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.constants import HttpMethod
    from cyberdrop_dl.network.request import RequestParams
    from cyberdrop_dl.url_objects import ScrapeItem


@final
class Selector:
    CAPTCHA = "h1:-soup-contains.own('Checkpoint | Sentinel')"
    NEXT_PAGE = "a.btn-ghost:-soup-contains(Next)[href*='search=']"
    ALBUMS = "main .grid a.group.card-hover"


_CAPTCHA_MSG = "CAPTCHA checkpoint found. Resolve on your browser, import cookies and use the same user-agent"


@URLConfig(allow_empty_path=True)
class BunkrAlbumsCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Search": "/?search=<query>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://balbums.st")
    DOMAIN: ClassVar[str] = "bunkr-albums"
    FOLDER_DOMAIN: ClassVar[str] = "Bunkr-Albums"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("bunkr-albums.io",)
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE

    @override
    async def __async_post_init__(self) -> None:
        async with self.catch_errors(self.PRIMARY_URL), self.disable_on_error("Checkpoint required"):
            if not self.cookies.get("cp_clr"):
                raise DDOSGuardError(_CAPTCHA_MSG)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [] | [""] if query := scrape_item.url.query.get("search"):
                await self.search(scrape_item, query)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        title = self.create_title(query)
        scrape_item.setup_as_profile(title)

        async for soup in self.web_pager(scrape_item.url.update_query(per=100)):
            for new_item in self.iter_children(scrape_item, soup, Selector.ALBUMS):
                self.handle_external_links(new_item)

    @override
    async def request_soup(
        self, url: AbsoluteHttpURL, /, method: HttpMethod = "GET", **kwargs: Unpack[RequestParams]
    ) -> BeautifulSoup:
        try:
            return await super().request_soup(url, method, **kwargs)
        except DownloadError as e:
            if e.status != 403:
                raise
            raise DDOSGuardError(_CAPTCHA_MSG) from None
