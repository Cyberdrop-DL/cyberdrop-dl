# https://e621.net/help/api
from __future__ import annotations

import operator
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.constants import CDL_USER_AGENT
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import Deduper
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from cyberdrop_dl.url_objects import ScrapeItem


@HTTPConfig(rate_limit=(2, 1), headers={"User-Agent": f"{CDL_USER_AGENT} (by B05FDD249DF29ED3)"})
class E621Crawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Post": "/posts/<post_id>",
        "Search": "/posts?tags=<tags>",
        "Pools": "/pools/<pool_id>",
        "Direct file": "https://static.e621.net/data/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://e621.net")
    DOMAIN: ClassVar[str] = "e621.net"
    FOLDER_DOMAIN: ClassVar[str] = "E621"

    def __post_init__(self) -> None:
        self.api: DanbooruAPI = DanbooruAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["posts"] if tags := scrape_item.url.query.get("tags"):
                await self.search(scrape_item, tags)
            case ["posts", post_id]:
                await self.post(scrape_item, post_id)
            case ["pools", pool_id]:
                await self.pool(scrape_item, pool_id)
            case ["data", _, *_] if self.is_subdomain(scrape_item.url):
                await self.direct_file(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, tags: str) -> None:
        scrape_item.setup_as_album(self.create_title(tags.replace("+", " ")))
        sleep = aio.periodic_sleep(10)
        async with (
            aio.non_cancelling_taskgroup() as tg,
            aio.maybe_aclosing(self.api.search(scrape_item.url.query)) as posts,
        ):
            async for post in posts:
                new_item = scrape_item.create_child(self.PRIMARY_URL / f"posts/{post['id']}")
                tg.create_task(self._post_task(new_item, post))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def pool(self, scrape_item: ScrapeItem, pool_id: str) -> None:
        pool = await self.api.pool(pool_id)
        scrape_item.setup_as_album(self.create_title(pool["name"], pool_id), album_id=pool_id)
        self.create_eager_task(self.write_metadata(scrape_item, f"pool_{pool_id}", pool))
        sleep = aio.periodic_sleep(10)
        for post_id in pool["post_ids"]:
            new_item = scrape_item.create_child(self.PRIMARY_URL / f"posts/{post_id}")
            self.create_task(self.run(new_item, check_referer=True))
            scrape_item.add_children()
            await sleep()

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, post_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        post = await self.api.post(post_id)
        await self._post(scrape_item, post)

    async def _post(self, scrape_item: ScrapeItem, post: dict[str, Any]) -> None:
        scrape_item.uploaded_at = self.parse_iso_date(post["created_at"])
        files = post["files"]
        if await self.check_complete_by_hash(scrape_item.url, "md5", files["meta"]["md5"]):
            return

        src = self.parse_url(files["original"]["url"])
        _, ext = self.get_filename_and_ext(src.name)
        await self.handle_file(
            src,
            scrape_item,
            src.name,
            ext,
            custom_filename=self.create_custom_filename(str(post["id"]), ext, file_id=Path(src.name).stem),
            metadata=post,
        )

    @error_handling_wrapper
    async def _post_task(self, scrape_item: ScrapeItem, post: dict[str, Any]) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        await self._post(scrape_item, post)


class DanbooruAPI(API):
    async def post(self, post_id: str) -> dict[str, Any]:
        url = self.PRIMARY_URL / f"posts/{post_id}.json"
        return await self.request_json(url)

    async def pool(self, pool_id: str) -> dict[str, Any]:
        url = self.PRIMARY_URL / f"pools/{pool_id}.json"
        resp = await self.request_json(url)
        resp["name"] = resp.get("name", f"Unknown Pool {pool_id}").replace("_", " ")
        return resp

    async def notes(self, post_id: str) -> list[dict[str, Any]]:
        url = (self.PRIMARY_URL / "notes.json").with_query({"search[post_id]": post_id})
        return await self.request_json(url)

    async def pools(self, post_id: str) -> list[dict[str, Any]]:
        url = (self.PRIMARY_URL / "pools.json").with_query({"search[post_id]": post_id})
        return await self.request_json(url)

    async def search(self, query: Mapping[str, str]) -> AsyncGenerator[dict[str, Any]]:
        get_key = operator.itemgetter("id")
        unique = Deduper(get_key).filter
        limit = int(query.get("limit") or 200)
        per_page = max(limit // 5, 0)
        order = "a" if query.get("page", "").startswith("a") else "b"

        url = (self.PRIMARY_URL / "posts.json").update_query(query)
        while True:
            posts = await self.request_json(url)
            if type(posts) is dict:
                posts = posts["posts"]

            posts = sorted(unique(posts), key=get_key, reverse=order == "a")
            for post in posts:
                yield post
            if len(posts) <= per_page:
                break

            url = url.update_query(page=f"{order}{posts[0]['id']}")
