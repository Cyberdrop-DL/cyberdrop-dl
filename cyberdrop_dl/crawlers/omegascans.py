from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


_API_ENTRYPOINT = AbsoluteHttpURL("https://api.omegascans.org/chapter/query")


class Selector:
    DATE = 'h2[class="font-semibold font-sans text-muted-foreground text-xs"]'
    SERIES_ID = "script:-soup-contains('series_id')"
    DATE_JS = "script:-soup-contains('created')"
    IMAGE = "p[class*=flex] img"


class OmegaScansCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Chapter": "/series/<series_name>/<slug>",
        "Series": "/series/<series_name>",
        "Direct links": "",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://omegascans.org")
    DOMAIN: ClassVar[str] = "omegascans"
    FOLDER_DOMAIN: ClassVar[str] = "OmegaScans"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["series", _]:
                return await self.series(scrape_item)
            case ["series", _, slug] if "chapter" in slug:
                return await self.chapter(scrape_item)
            case _:
                await self.handle_direct_link(scrape_item)

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

        scrape_item.part_of_album = True
        title_parts = css.select_text(soup, "title").split(" - ")
        series_name, chapter_title = title_parts[:2]
        series_title = self.create_title(series_name)
        scrape_item.add_to_parent_title(series_title)
        scrape_item.add_to_parent_title(chapter_title)

        date_str = soup.select(Selector.DATE)[-1].get_text()
        date = self.parse_date(date_str)
        if not date:
            date_str = css.select_text(soup, Selector.DATE_JS).split('created_at\\":\\"')[1].split(".")[0]
            date = self.parse_date(date_str)

        scrape_item.uploaded_at = date
        for attribute in ("src", "data-src"):
            for _, link in self.iter_tags(soup, Selector.IMAGE, attribute):
                filename, ext = self.get_filename_and_ext(link.name)
                await self.handle_file(link, scrape_item, filename, ext)

    @error_handling_wrapper
    async def handle_direct_link(self, scrape_item: ScrapeItem) -> None:
        """Handles a direct link."""
        scrape_item.url = scrape_item.url.with_query(None)
        filename, ext = self.get_filename_and_ext(scrape_item.url.name)
        await self.handle_file(scrape_item.url, scrape_item, filename, ext)
