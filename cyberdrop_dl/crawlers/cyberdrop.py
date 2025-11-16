from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem

_API_ENTRYPOINT = AbsoluteHttpURL("https://api.cyberdrop.cr/api/")
_PRIMARY_URL = AbsoluteHttpURL("https://cyberdrop.cr/")


class Selector:
    ALBUM_TITLE = "#title"
    ALBUM_DATE = ".level-item p:-soup-contains(Uploaded) + p"
    ALBUM_ITEM = "a#file"


class CyberdropCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "k1-cd.cdn.gigachad-cdn.ru", "cyberdrop"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/a/<album_id>",
        "File": (
            "/f/<file_id>",
            "/e/<file_id>",
        ),
        "Direct links": "/api/file/d/<file_id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = _PRIMARY_URL
    DOMAIN: ClassVar[str] = "cyberdrop"
    OLD_DOMAINS = ("cyberdrop.me", "cyberdrop.to")
    _RATE_LIMIT: ClassVar[tuple[float, float]] = 5, 1
    _DOWNLOAD_SLOTS: ClassVar[int | None] = 1

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["a", album_id, *_]:
                return await self.album(scrape_item, album_id)
            case ["api", "file" | "proxy", "d" | "auth" | "thumb", file_id, *_]:
                return await self.file(scrape_item, file_id)
            case ["f" | "e", file_id]:
                return await self.file(scrape_item, file_id)
            case [_]:
                return await self.follow_redirect(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        scrape_item.url = scrape_item.url.with_query("nojs")
        soup = await self.request_soup(scrape_item.url)
        title = css.select_one_get_text(soup, Selector.ALBUM_TITLE)
        title = self.create_title(title, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        date_str = css.select_one_get_text(soup, Selector.ALBUM_DATE)
        scrape_item.possible_datetime = self.parse_date(date_str, "%d.%m.%Y")

        for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.ALBUM_ITEM):
            self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, file_id: str) -> None:
        scrape_item.url = self.PRIMARY_URL / "f" / file_id
        if await self.check_complete_from_referer(scrape_item):
            return

        info, auth = await asyncio.gather(
            self.request_json(_API_ENTRYPOINT / "file" / "info" / file_id),
            self.request_json(_API_ENTRYPOINT / "file" / "auth" / file_id),
        )

        name: str = info["name"]
        filename, ext = self.get_filename_and_ext(name)
        link = self.parse_url(auth["url"])
        await self.handle_file(link, scrape_item, name, ext, custom_filename=filename)


def fix_db_referer(referer: str) -> str:
    url = AbsoluteHttpURL(referer)
    return str(CyberdropCrawler.transform_url(url))
