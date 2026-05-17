from __future__ import annotations

import dataclasses
import itertools
from typing import TYPE_CHECKING, Any, ClassVar, override

from cyberdrop_dl.crawlers.crawler import Crawler, CrawlerAPI, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import error_handling_wrapper, parse_url

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.url_objects import ScrapeItem


@dataclasses.dataclass(slots=True, kw_only=True)
class Chapter:
    name: str
    slug: str
    created_at: str
    series_title: str
    images: tuple[AbsoluteHttpURL, ...]


class OmegaScansCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Chapter": "/series/<series_name>/<slug>",
        "Series": "/series/<series_name>",
        "Direct links": "/file/....",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://omegascans.org")
    DOMAIN: ClassVar[str] = "omegascans"
    FOLDER_DOMAIN: ClassVar[str] = "OmegaScans"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["series", series_slug]:
                return await self.series(scrape_item, series_slug)
            case ["series", series_slug, chapter_slug]:
                return await self.chapter(scrape_item, series_slug, chapter_slug)
            case ["file", *_]:
                await self.direct_file(scrape_item)
            case _:
                raise ValueError

    @override
    async def __async_post_init__(self) -> None:
        self.api: OmegaScansAPI = OmegaScansAPI(self)

    @error_handling_wrapper
    async def series(self, scrape_item: ScrapeItem, series_slug: str) -> None:
        scrape_item.setup_as_album("", album_id=series_slug)
        async for chapter_slugs in self.api.series_chapters(series_slug):
            for slug in chapter_slugs:
                chapter_url = self.PRIMARY_URL / "series" / series_slug / slug
                new_scrape_item = scrape_item.create_child(chapter_url)
                self.create_task(self.run(new_scrape_item))
                scrape_item.add_children()

    @error_handling_wrapper
    async def chapter(self, scrape_item: ScrapeItem, series_slug: str, chapter_slug: str) -> None:
        chapter = await self.api.chapter(series_slug, chapter_slug)
        scrape_item.setup_as_album(self.create_title(chapter.series_title))
        scrape_item.add_to_parent_title(chapter.name)
        scrape_item.uploaded_at = self.parse_iso_date(chapter.created_at)
        for img in chapter.images:
            self.create_task(self.direct_file(scrape_item, img))
            scrape_item.add_children()


class OmegaScansAPI(CrawlerAPI):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.omegascans.org")

    async def chapter(self, series_slug: str, chapter_slug: str) -> Chapter:
        api_url = self.ENTRYPOINT / "chapter" / series_slug / chapter_slug
        resp = await self.request_json(api_url)
        if resp.get("paywall"):
            raise ScrapeError(
                402, "This is a premium chapter. You need to be a subscriber or buy this chapter to access its content"
            )
        chapter = resp["chapter"]
        return Chapter(
            name=chapter["chapter_name"],
            slug=chapter["chapter_slug"],
            created_at=chapter["created_at"],
            images=tuple(map(parse_url, chapter["chapter_data"]["images"])),
            series_title=chapter["series"]["title"],
        )

    async def series_chapters(self, series_slug: str) -> AsyncGenerator[tuple[str,]]:
        api_url = self.ENTRYPOINT / "series" / series_slug
        series_id: int = (await self.request_json(api_url))["id"]
        api_url = (self.ENTRYPOINT / "chapter/query").with_query(series_id=series_id, perPage=10_000)
        for page in itertools.count(1):
            resp: dict[str, Any] = await self.request_json(api_url.update_query(page=page))
            yield tuple(data["chapter_slug"] for data in resp["data"])
            if resp["meta"]["current_page"] == resp["meta"]["last_page"]:
                break
