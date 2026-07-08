from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._kvs import KernelVideoSharingCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedPaths
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    _MEMBER_NAME = "div.channel_logo > h2.title"
    _MODEL_NAME = ".brand_inform > .title"
    _TAG_NAME = "h1.title"
    TITLE = ", ".join((_MEMBER_NAME, _MODEL_NAME, _TAG_NAME))
    THUMBS = "div.item.thumb > a.th"


class Rule34VideoCrawler(KernelVideoSharingCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Search": "/search/<query>",
        "Category": "/categories/<name>",
        "Tag": "/tags/<name>",
        "Video": "/video/<id>/<slug>",
        "Members": "/members/<member_id>",
        "Model": "/models/<name>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://rule34video.com/")
    DOMAIN: ClassVar[str] = "rule34video"
    FOLDER_DOMAIN: ClassVar[str] = "Rule34Video"

    async def __async_post_init__(self) -> None:
        self.update_cookies(
            {
                "kt_rt_popAccess": 1,
                "kt_tcookie": 1,
            }
        )

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video" | "videos", _, *_]:
                return await self.video(scrape_item)
            case ["search" as type_, query]:
                return await self.search(scrape_item, type_, query)
            case ["tags" | "categories" | "members" | "models" as type_, _]:
                return await self.search(scrape_item, type_)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, type_: str, query: str | None = None) -> None:
        soup = await self.request_soup(scrape_item.url)
        title = css.select_text(soup, Selector.TITLE, decompose="span")
        for trash in ("Videos for: ", "Tagged with "):
            title = title.removeprefix(trash)

        title = self.create_title(f"{title} [{type_}]")
        scrape_item.setup_as_album(title)

        for new_scrape_item in self.iter_children(scrape_item, soup, Selector.THUMBS):
            self.create_task(self.run(new_scrape_item))

        await self._iter_extra_pages(scrape_item, type_, query)

    async def _iter_extra_pages(self, scrape_item: ScrapeItem, type_: str, query: str | None = None) -> None:
        if type_ == "members":
            block_id, from_name = "list_videos_uploaded_videos", "from_videos"

        elif type_ == "search":
            block_id, from_name = "custom_list_videos_videos_list_search", "from_videos"

        else:
            block_id, from_name = "custom_list_videos_common_videos", "from"

        async for soup in self._ajax_pagination(
            scrape_item.url,
            block_id=block_id,
            sort_by="post_date",
            q=query,
            from_query_param_name=from_name,
        ):
            for new_scrape_item in self.iter_children(scrape_item, soup, Selector.THUMBS):
                self.create_task(self.run(new_scrape_item))
