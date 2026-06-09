from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper, open_graph

if TYPE_CHECKING:
    from bs4 import BeautifulSoup, Tag

    from cyberdrop_dl.url_objects import ScrapeItem


_M3U8_SERVER = AbsoluteHttpURL("https://surrit.com/")
_COLLECTION_TYPES = "makers", "search", "genres", "labels", "tags"


class Selector:
    UUID = "script:-soup-contains('m3u8|')"
    DATE = "div > span:-soup-contains('Release date:') + time"
    DVD_CODE = "div > span:-soup-contains('Code:') + span"
    NEXT_PAGE = "nav a[rel=next]"
    ITEM = ".grid .thumbnail.group a"


class MissAVCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/...",
        **{name.capitalize(): f"/{name}/<{name.removesuffix('s')}>" for name in _COLLECTION_TYPES},
    }
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "njavtv.com", "missav.ws"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://missav.ws")
    DOMAIN: ClassVar[str] = "missav"
    FOLDER_DOMAIN: ClassVar[str] = "MissAV"
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    _IMPERSONATE: ClassVar[str | bool | None] = True

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [*_, collection_type, name] if collection_type in _COLLECTION_TYPES:
                return await self.collection(scrape_item, collection_type, name)
            case [*_, video_id]:
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def collection(self, scrape_item: ScrapeItem, collection_type: str, name: str) -> None:
        title = self.create_title(f"{name} [{collection_type}]")
        scrape_item.setup_as_album(title)

        async for soup in self.web_pager(scrape_item.url.update_query(page=1)):
            for new_scrape_item in self.iter_children(scrape_item, soup, Selector.ITEM):
                self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        scrape_item.url = canonical_url = self.PRIMARY_URL / "en" / video_id
        if await self.check_complete_from_referer(canonical_url):
            return

        soup = await self.request_soup(scrape_item.url)

        title = open_graph.title(soup)
        if dvd_code_tag := soup.select_one(Selector.DVD_CODE):
            title = _fix_title(title, dvd_code_tag)

        scrape_item.uploaded_at = self.parse_iso_date(
            open_graph.get("video_release_date", soup) or css.select(soup, Selector.DATE, "datetime")
        )

        uuid = _extract_uuid(soup)
        m3u8_url = _M3U8_SERVER / uuid / "playlist.m3u8"
        m3u8, info = await self.request_m3u8_playlist(
            m3u8_url,
            headers={"Referer": "https://missav.ws/"},
        )
        filename = self.create_custom_filename(title, ext := ".mp4", resolution=info.resolution)
        await self.handle_file(m3u8_url, scrape_item, title, ext, m3u8=m3u8, custom_filename=filename)


def _extract_uuid(soup: BeautifulSoup) -> str:
    js_text = css.select_text(soup, Selector.UUID)
    uuid_joined_parts = js_text.split("m3u8|", 1)[-1].split("|com|surrit", 1)[0]
    uuid_parts = reversed(uuid_joined_parts.split("|"))
    return "-".join(uuid_parts)


def _fix_title(title: str, dvd_code_tag: Tag) -> str:
    dvd_code = css.text(dvd_code_tag).upper()
    uncensored = "UNCENSORED" in dvd_code
    leak = "LEAK" in dvd_code
    for trash in ("-UNCENSORED", "-LEAK"):
        dvd_code = dvd_code.replace(trash, "").removesuffix("-")

    title = " ".join(word for word in title.split(" ") if dvd_code not in word.upper())
    full_dvd_code = f"{dvd_code}{(uncensored and '-UNCENSORED') or ''}{(leak and '-LEAK') or ''}"
    return f"{full_dvd_code} {title}"
