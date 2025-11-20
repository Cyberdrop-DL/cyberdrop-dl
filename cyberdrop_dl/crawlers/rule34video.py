from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._kvs import KernelVideoSharingCrawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedPaths
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class Selector:
    MEMBER_NAME = "div.channel_logo > h2.title"
    MODEL_NAME = ".brand_inform > .title"
    TAG_NAME = "h1.title"
    TITLE = ", ".join((MEMBER_NAME, MODEL_NAME, TAG_NAME))

    THUMBS = "div.item.thumb > a.th"
    NEXT_PAGE = "div.item.pager.next > a"


class Rule34VideoCrawler(KernelVideoSharingCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Members": "/members/...",
        "Models": "/models/...",
        "Search": "/search/...",
        "Tags": "/tags/...",
        "Video": (
            "/video/<id>/<name>",
            "/videos/<id>/<name>",
        ),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://rule34video.com/")
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    DOMAIN: ClassVar[str] = "rule34video"
    FOLDER_DOMAIN: ClassVar[str] = "Rule34Video"

    async def async_startup(self) -> None:
        self.update_cookies({"kt_rt_popAccess": 1, "kt_tcookie": 1})

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video" | "videos", _, *_]:
                return await self.video(scrape_item)
            case ["tags" | "search" | "categories" | "members" | "models" as type_, _, *_]:
                return await self.collection(scrape_item, type_)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def collection(self, scrape_item: ScrapeItem, type_: str) -> None:
        title: str = ""
        async for soup in self.web_pager(scrape_item.url):
            if not title:
                title_tag = css.select_one(soup, Selector.TITLE)
                css.decompose(title_tag, "span")
                title = css.get_text(title_tag)
                for trash in ("Videos for: ", "Tagged with "):
                    title = title.removeprefix(trash)

                title = self.create_title(f"{title} [{type_}]")
                scrape_item.setup_as_album(title)

            for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.THUMBS):
                self.create_task(self.run(new_scrape_item))
