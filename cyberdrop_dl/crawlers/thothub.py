from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._kvs import KernelVideoSharingCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedPaths
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    TITLE = ".main-container .headline h1"
    VIDEOS = ".list-videos .item a"


class ThotHubCrawler(KernelVideoSharingCrawler, ensure_trailing_slash=True):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/albums/<id>/<name>",
        "Image": "/get_image/...",
        "Video": "/videos/<id>/<slug>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://thothub.to")
    DEFAULT_TRIM_URLS: ClassVar[bool] = False
    DOMAIN: ClassVar[str] = "thothub"
    FOLDER_DOMAIN: ClassVar[str] = "ThotHub"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:-1]:
            case ["albums", album_id, _]:
                return await self.album(scrape_item, album_id)
            case ["videos", _, _]:
                return await self.video(scrape_item)
            case ["categories" | "tags" as type_, _]:
                return await self.search(scrape_item, type_)
            case ["search" as type_, query]:
                return await self.search(scrape_item, type_, query)
            case ["get_image", _, *_]:
                return await self.direct_file(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, type_: str, query: str | None = None) -> None:
        soup = await self.request_soup(scrape_item.url)
        title = self._clean_title(css.select_text(soup, Selector.TITLE))
        title = self.create_title(f"{title} [{type_}]")
        scrape_item.setup_as_album(title)

        for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.VIDEOS):
            self.create_task(self.run(new_scrape_item))

        await self._iter_extra_pages(scrape_item, type_, query)

    async def _iter_extra_pages(self, scrape_item: ScrapeItem, type_: str, query: str | None = None) -> None:
        if type_ == "search":
            block_id, from_name = "list_videos_videos_list_search_result", "from_videos"
        else:
            block_id, from_name = "list_videos_common_videos_list", "from"

        async for soup in self._ajax_pagination(
            scrape_item.url,
            block_id=block_id,
            sort_by="post_date",
            q=query,
            from_query_param_name=from_name,
        ):
            for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.VIDEOS):
                self.create_task(self.run(new_scrape_item))
