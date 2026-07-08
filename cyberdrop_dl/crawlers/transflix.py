from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, open_graph
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem

_UNIX_TIMESTAMP_LENGTH: int = 10


class Selector:
    VIDEO = "video#player > source"
    SEARCH_RESULTS = "div.list-videos div.item > a"
    NEXT_PAGE = "li.next > a"


class TransflixCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/video/<name>-<video_id>",
        "Search": "/search/?q=<query>",
    }
    DOMAIN: ClassVar[str] = "transflix"
    FOLDER_DOMAIN: ClassVar[str] = "TransFlix"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://transflix.net")
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    _RATE_LIMIT: ClassVar[RateLimit] = 3, 2

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video", slug] if video_id := slug.rsplit("-", 1)[-1]:
                return await self.video(scrape_item, video_id)
            case ["search"] if query := scrape_item.url.query.get("q"):
                return await self.search(scrape_item, query)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return None

        soup = await self.request_soup(scrape_item.url)
        title = open_graph.title(soup)
        video = css.select(soup, Selector.VIDEO, "src")
        link = self.parse_url(video)
        filename, ext = self.get_filename_and_ext(link.name)
        scrape_item.uploaded_at = _timestamp_from_filename(link.name)
        custom_filename = self.create_custom_filename(title, ext, file_id=video_id)

        return await self.handle_file(link, scrape_item, filename, ext, custom_filename=custom_filename)

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        title = self.create_title(f"Search - {query}")
        scrape_item.setup_as_album(title)

        async for soup in self.web_pager(scrape_item.url, Selector.NEXT_PAGE):
            for new_scrape_item in self.iter_children(scrape_item, soup, Selector.SEARCH_RESULTS):
                self.create_task(self.run(new_scrape_item))


def _timestamp_from_filename(filename: str) -> int | None:
    stem = Path(filename).stem
    if len(stem) >= _UNIX_TIMESTAMP_LENGTH:
        possible_timestamp = stem[-_UNIX_TIMESTAMP_LENGTH:]
        try:
            return int(possible_timestamp)
        except ValueError:
            return None
