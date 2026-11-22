from __future__ import annotations

import itertools
import operator
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypedDict, cast

from cyberdrop_dl import aio
from cyberdrop_dl.constants import CDL_USER_AGENT
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.network.http import HTTPConfig
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import Deduper
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from cyberdrop_dl.url_objects import ScrapeItem


@HTTPConfig(rate_limit=(2, 1), headers={"User-Agent": CDL_USER_AGENT})
class DanBooruGenericCrawler(Crawler, is_generic=True):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Post": (
            "/post/<post_id>",
            "/posts/<post_id>",
            "/p/<post_id>",
            "/show/<post_id>",
        ),
        "Search": "/posts?tags=<tags>",
        "Pools": (
            "/pool/<pool_id>",
            "/pools/<pool_id>",
        ),
        "Direct file": "/data/...",
    }

    CDN: ClassVar[AbsoluteHttpURL]

    def __post_init__(self) -> None:
        self.api: DanbooruAPI = DanbooruAPI.from_crawler(self)
        self.api.cdn = self.CDN

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["posts"] if tags := scrape_item.url.query.get("tags"):
                await self.search(scrape_item, tags)
            case ["posts" | "p" | "show" | "post", post_id]:
                await self.post(scrape_item, post_id)
            case ["pools" | "pool", pool_id]:
                await self.pool(scrape_item, pool_id)
            case ["data", _, *_]:
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
        scrape_item.url = scrape_item.url.with_query(None)
        if await self.check_complete_from_referer(scrape_item.url):
            return

        post = await self.api.post(post_id)
        await self._post(scrape_item, post)

    async def _post(self, scrape_item: ScrapeItem, post: Post) -> None:
        scrape_item.uploaded_at = self.parse_iso_date(post["created_at"])
        file = post["file"]
        if await self.check_complete_by_hash(scrape_item.url, "md5", file["md5"]):
            return

        src = self.parse_url(file["url"])
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
    async def _post_task(self, scrape_item: ScrapeItem, post: Post) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        await self._post(scrape_item, post)


class Post(TypedDict):
    id: int
    created_at: str
    file: dict[str, str]
    md5: str
    ext: str
    url: str | None


@HTTPConfig(headers={"User-Agent": CDL_USER_AGENT})
class DanbooruAPI(API):
    cdn: AbsoluteHttpURL

    def _normalize_post(self, post: dict[str, Any]) -> Post:
        "Transform v2 post to v1-like post with a 'file' key"
        post = post.get("post", post)
        try:
            file = post["file"]
        except KeyError:
            try:
                files = post["files"]
            except KeyError:
                file = {"md5": post["md5"], "url": post["file_url"]}
            else:
                file = files["meta"] | files["original"]

        if not file.get("url"):
            md5 = file["md5"]
            name = f"{md5}.{file['ext']}"
            file["url"] = str(self.cdn / f"data/{md5[0:2]}/{md5[2:4]}/{name}")

        post["file"] = file
        return cast("Post", cast("object", post))

    async def post(self, post_id: str) -> Post:
        url = self.PRIMARY_URL / f"posts/{post_id}.json"
        resp = await self.request_json(url)
        return self._normalize_post(resp)

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

    def _skip(self, post: Post) -> bool:
        # TODO: fix this
        return False
        flags = post.get("flags", post)
        for reason in ("deleted", "pending", "is_deleted", "is_pending"):
            if flags.get(reason):
                self.log.warning("Skipping post %s [%s]", post["id"], reason)
                return True
        return False

    @classmethod
    def _select_order(cls, query: Mapping[str, str]) -> Literal["a", "b"] | None:
        tags = query.get("tags", "").replace("+", " ").split()
        for tag in tags:
            if ":" not in tag:
                continue

            name, _, value = tag.partition(":")
            if name in {"id", "md5", "ordfav", "ordfavgroup", "ordpool"}:
                return None
            if name == "order":
                if value in {"id", "id_asc"}:
                    return "a"
                if value == "id_desc":
                    return "b"
                return None

        return "a" if query.get("page", "").startswith("a") else "b"

    async def search(self, query: Mapping[str, str]) -> AsyncGenerator[Post]:
        get_key = operator.itemgetter("id")
        unique = Deduper(get_key).filter
        limit = int(query.get("limit") or 200)
        per_page = max(limit // 5, 0)
        order = self._select_order(query)

        url = (self.PRIMARY_URL / "posts.json").update_query(query).update_query(limit=limit)
        while True:
            posts = await self.request_json(url)
            if type(posts) is dict:
                posts = posts["posts"]

            posts = sorted(map(self._normalize_post, posts), key=get_key, reverse=order == "a")
            for post in unique(posts):
                if self._skip(post):
                    continue
                yield post

            if len(posts) <= per_page:
                break

            page = f"{order}{posts[0]['id']}" if order else (int(url.query.get("page", 1)) + 1)
            url = url.update_query(page=page)


class DanBooruCrawler(DanBooruGenericCrawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = tuple(
        itertools.chain.from_iterable(
            (f"{sub}donmai.us", f"{sub}donmai.moe")
            for sub in (
                "",
                "safebooru.",
                "sonohara.",
                "danbooru.",
                "shima.",
            )
        )
    )

    SUPPORTED_PATHS: ClassVar[SupportedPaths] = DanBooruGenericCrawler.SUPPORTED_PATHS | {
        "Post": ("/posts/<post_id>",),
        "Pools": ("/pool/<pool_id>",),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://danbooru.donmai.us")
    DOMAIN: ClassVar[str] = "danbooru"
    CDN: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://cdn.donmai.us")


class BleachBooruCrawler(DanBooruCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://bleachbooru.org")
    DOMAIN: ClassVar[str] = "bleachbooru"
    FOLDER_DOMAIN: ClassVar[str] = "BleachBooru"
    CDN: ClassVar[AbsoluteHttpURL] = PRIMARY_URL


class BorvarBooruCrawler(DanBooruCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://booru.borvar.art")
    DOMAIN: ClassVar[str] = "booru.borvar.art"
    FOLDER_DOMAIN: ClassVar[str] = "BorvarArt"
    CDN: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
