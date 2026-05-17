from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.constants import CDL_USER_AGENT
from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.url_objects import ScrapeItem


class E621Crawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Post": "/posts/<post_id>",
        "Tags": "/posts?tags=<tags>",
        "Pools": "/pools/<pool_id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://e621.net")
    DOMAIN: ClassVar[str] = "e621.net"
    FOLDER_DOMAIN: ClassVar[str] = "E621"
    _RATE_LIMIT: ClassVar[RateLimit] = 2, 1

    def __post_init__(self) -> None:
        self.headers = {
            "User-Agent": f"{CDL_USER_AGENT} (by B05FDD249DF29ED3)",
        }

    async def fetch(self, scrape_item: ScrapeItem) -> None:

        match scrape_item.url.parts[1:]:
            case ["posts"] if tags := scrape_item.url.query.get("tags"):
                return await self.tags(scrape_item, tags)
            case ["posts", post_id]:
                return await self.post(scrape_item, post_id)
            case ["pools", pool_id]:
                return await self.pool(scrape_item, pool_id)
            case _:
                raise ValueError

    async def _pager(self, scrape_item: ScrapeItem) -> AsyncGenerator[list[dict[str, Any]]]:
        initial_page = int(scrape_item.url.query.get("page", 1))
        url = (self.PRIMARY_URL / "posts.json").with_query(tags=scrape_item.url.query["tags"])
        for page in itertools.count(initial_page):
            resp: dict[str, Any] = await self.request_json(url.update_query(page=page), headers=self.headers)
            posts = resp.get("posts", [])
            if not posts:
                break
            yield posts

    @error_handling_wrapper
    async def tags(self, scrape_item: ScrapeItem, tags: str) -> None:
        title = self.create_title(tags.replace("+", " "))
        scrape_item.setup_as_album(title)

        async for posts in self._pager(scrape_item):
            for post in posts:
                try:
                    file_url = post["file"]["url"]
                except KeyError:
                    continue

                new_scrape_item = scrape_item.create_child(self.parse_url(file_url))
                new_scrape_item.uploaded_at = self.parse_iso_date(post["created_at"])
                self.create_task(self.direct_file(new_scrape_item))
                scrape_item.add_children()

    @error_handling_wrapper
    async def pool(self, scrape_item: ScrapeItem, pool_id: str) -> None:
        url = self.PRIMARY_URL / f"pools/{pool_id}.json"
        resp: dict[str, Any] = await self.request_json(url, headers=self.headers)
        posts = resp.get("post_ids", [])
        title: str = resp.get("name", "Unknown Pool").replace("_", " ")
        scrape_item.setup_as_album(title)

        for post_id in posts:
            url = self.PRIMARY_URL / f"posts/{post_id}"
            new_scrape_item = scrape_item.create_child(url)
            self.create_task(self.run(new_scrape_item))
            scrape_item.add_children()

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, post_id: str) -> None:
        url = self.PRIMARY_URL / f"posts/{post_id}.json"
        resp: dict[str, Any] = await self.request_json(url, headers=self.headers)
        file_url: str = resp["post"]["file"]["url"]
        await self.direct_file(scrape_item, self.parse_url(file_url))
