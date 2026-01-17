from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from yarl import URL

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class Selector:
    ALBUMS = "#listView a.album-row"
    ALBUM_FILES = "#fileTbody tr[data-id]"
    MD5 = "div:-soup-contains('Checksum (MD5)') + div"
    UPLOAD_DATE = "svg.h-4.w-4 + span"
    NEXT_PAGE = "a:-soup-contains(Next)[href*='?page']"


class TurboVidCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/a/<album_id>",
        "Video": ("/embed/<file_id>", "/d/<file_id>", "/v/<file_id>"),
        "Search": "library?q=<query>",
        "Direct links": "/data/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://turbovid.cr")
    DOMAIN: ClassVar[str] = "turbovid.cr"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("turbo.cr",)
    FOLDER_DOMAIN: ClassVar[str] = "TurboVid"
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["library", *_] if query := scrape_item.url.query.get("q"):
                return await self.search(scrape_item, query)
            case ["a", album_id, *_]:
                return await self.album(scrape_item, album_id)
            case ["embed" | "d" | "v", file_id, *_]:
                return await self.video(scrape_item, file_id)
            case ["data" | "videos", _, *_]:
                return await self.direct_file(scrape_item)
            case _:
                raise ValueError

    def __post_init__(self) -> None:
        # Re-define instances as saint crawler to share DB entries
        # TODO: delete saint crawler when turbovid is out of beta
        # TODO: rename old saint DB entries to turbovid
        self.DOMAIN = "saint"

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        title = self.create_title(f"{query} [search]")
        scrape_item.setup_as_album(title)
        async for soup in self.web_pager(scrape_item.url):
            for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.ALBUMS):
                self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        name = css.page_title(soup).removesuffix(" - turbovid.cr")
        title = self.create_title(name, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        for row in soup.select(Selector.ALBUM_FILES):
            file_id = css.get_attr(row, "data-id")
            web_url = self.PRIMARY_URL / "d" / file_id
            new_scrape_item = scrape_item.create_child(web_url)
            self.create_task(self.run(new_scrape_item))
            scrape_item.add_children()

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, file_id: str) -> None:
        scrape_item.url = self.PRIMARY_URL / "d" / file_id
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        checksum = css.select_text(soup, Selector.MD5)
        if await self.check_complete_by_hash(scrape_item, "md5", checksum):
            return

        scrape_item.possible_datetime = self.parse_iso_date(css.select_text(soup, Selector.UPLOAD_DATE))
        sign_url = (self.PRIMARY_URL / "api/sign").with_query(v=file_id)
        link = self.parse_url((await self.request_json(sign_url))["url"])
        await self.direct_file(scrape_item, link)

    async def check_complete_from_referer(self, scrape_item: ScrapeItem | URL, any_crawler: bool = False) -> bool:
        downloaded = await super().check_complete_from_referer(scrape_item)
        if not downloaded:
            saint_url = scrape_item.url.with_host("saint2.cr")
            downloaded = await super().check_complete_from_referer(saint_url)
        return downloaded
