from __future__ import annotations

import dataclasses
import itertools
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper, next_js

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


_API_ENTRYPOINT = AbsoluteHttpURL("https://api.omegascans.org/chapter/query")


class Selector:
    SERIES_ID = "script:-soup-contains('series_id')"
    IMAGE = "#content  img.h-auto.object-contain"


@dataclasses.dataclass(slots=True)
class Chapter:
    name: str
    slug: str
    created_at: str


@dataclasses.dataclass(slots=True)
class Series:
    title: str
    thumbnail: str
    slug: str


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
            case ["series", _]:
                return await self.series(scrape_item)
            case ["series", _, _]:
                return await self.chapter(scrape_item)
            case ["file", *_]:
                await self.direct_file(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def series(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)
        js_script = css.select_text(soup, Selector.SERIES_ID)
        series_id = js_script.split('series_id\\":')[1].split(",")[0]
        scrape_item.setup_as_album("", album_id=series_id)
        # TODO: Add title
        # title: str = ""
        api_url = _API_ENTRYPOINT.with_query(series_id=series_id, perPage=30)

        for page in itertools.count(1):
            json_resp: dict[str, Any] = await self.request_json(api_url.update_query(page=page))
            for chapter in json_resp["data"]:
                chapter_url = scrape_item.url / chapter["chapter_slug"]
                new_scrape_item = scrape_item.create_child(chapter_url)
                self.create_task(self.run(new_scrape_item))
                scrape_item.add_children()

            if json_resp["meta"]["current_page"] == json_resp["meta"]["last_page"]:
                break

    @error_handling_wrapper
    async def chapter(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)

        if "This chapter is premium" in soup.get_text():
            raise ScrapeError(401, "This chapter is premium")

        series, chapter = _extract_info(soup)
        scrape_item.setup_as_album(self.create_title(series.title))
        scrape_item.add_to_parent_title(chapter.name)

        scrape_item.uploaded_at = self.parse_iso_date(chapter.created_at)
        for _, link in self.iter_tags(soup, Selector.IMAGE, "src"):
            self.create_task(self.direct_file(scrape_item, link))
            scrape_item.add_children()


def _extract_info(soup: BeautifulSoup) -> tuple[Series, Chapter]:
    data = next_js.extract(soup)
    chapter = next_js.find(data, "id", "series_id", "chapter_title", "created_at")
    series = next_js.find(data, "id", "series_slug", "title")
    return Series(
        title=series["title"],
        slug=series["series_slug"],
        thumbnail=series["thumbnail"],
    ), Chapter(
        name=chapter["chapter_name"],
        slug=chapter["chapter_slug"],
        created_at=chapter["created_at"],
    )
