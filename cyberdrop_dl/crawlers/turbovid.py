from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, override

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    ALBUMS = "#listView a.album-row"
    ALBUM_FILES = "#fileTbody tr[data-id]"
    MD5 = "div:-soup-contains('Checksum (MD5)') + div"
    UPLOAD_DATE = "svg.h-4.w-4 + span"
    NEXT_PAGE = "a:-soup-contains(Next)[href*='?page']"


class TurboVidCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/a/<album_id>",
        "Video": (
            "/embed/<file_id>",
            "/d/<file_id>",
            "/v/<file_id>",
        ),
        "Direct links": "/data/<file_id>.mp4",
        "Search": "library?q=<query>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://turbo.cr")
    DOMAIN: ClassVar[str] = "turbovid"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("turbovid.cr", "saint.to", "saint2.su", "saint2.cr")
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
            case _:
                raise ValueError

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["data", slug] if slug.endswith(suffix := ".mp4") and (video_id := slug.removesuffix(suffix)):
                return cls.PRIMARY_URL / "d" / video_id
            case _:
                return url

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
        name = css.select_text(soup, "h1")
        title = self.create_title(name, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        for row in soup.select(Selector.ALBUM_FILES):
            file_id = css.attr(row, "data-id")
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

        scrape_item.uploaded_at = self.parse_iso_date(css.select_text(soup, Selector.UPLOAD_DATE))
        name, dl_link = await self._request_download(file_id)
        filename, ext = self.get_filename_and_ext(name)
        await self.handle_file(dl_link, scrape_item, name, ext, custom_filename=filename)

    async def _request_download(self, file_id: str) -> tuple[str, AbsoluteHttpURL]:
        sign_url = (self.PRIMARY_URL / "api/sign").with_query(v=file_id)
        resp: dict[str, Any] = await self.request_json(sign_url)
        name: str = resp.get("original_filename") or resp["filename"]
        return name, self.parse_url(resp["url"])


def fix_db_referer(referer: str) -> str:
    url = AbsoluteHttpURL(referer.replace("/embed/", "/d/"))
    return str(TurboVidCrawler.transform_url(url))
