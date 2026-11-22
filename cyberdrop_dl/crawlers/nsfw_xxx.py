from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, override

from cyberdrop_dl import aio
from cyberdrop_dl.cache import disk_cached_method
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths, auto_task_id
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterable

    from cyberdrop_dl.url_objects import ScrapeItem


class NsfwXXXCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Post": "/post/<id>",
        "User": "/user/<username>",
        "Subreddit": "/r/<subreddit>",
        "Category": "/category/<name>",
        "Search": "/search?q=<query>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://nsfw.xxx")
    DOMAIN: ClassVar[str] = "nsfw.xxx"
    FOLDER_DOMAIN: ClassVar[str] = DOMAIN
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date:%Y-%m} - {title} [{id}]"

    def __post_init__(self) -> None:
        self.update_cookies({"auth.strategy": "custom"})
        self.api: NsfwXXXAPI = NsfwXXXAPI.from_crawler(self)

    @override
    async def __async_post_init__(self) -> None:
        with self.disable_on_error("Unable to get API token"):
            await self.api.refresh_token()

    @property
    def separate_posts(self) -> bool:
        return True

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["post", post_id]:
                await self.post(scrape_item, post_id)
            case ["user", user]:
                await self.user(scrape_item, user)
            case ["r", subreddit]:
                await self.subreddit(scrape_item, subreddit)
            case ["category", name]:
                await self.category(scrape_item, name)
            case ["search"] if query := scrape_item.url.query.get("q"):
                await self.search(scrape_item, query)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def subreddit(self, scrape_item: ScrapeItem, subreddit: str) -> None:
        data, pages = await aio.peek_next(self.api.subreddit(subreddit))
        name = data["subreddit"]["name"].removeprefix("/r/")
        scrape_item.setup_as_profile(self.create_title(name))
        await self._iter_posts(scrape_item, pages)

    @error_handling_wrapper
    async def category(self, scrape_item: ScrapeItem, name: str) -> None:
        data, pages = await aio.peek_next(self.api.category(name))
        scrape_item.setup_as_profile(self.create_title(data["category"]["name"]))
        await self._iter_posts(scrape_item, pages)

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        scrape_item.setup_as_profile(self.create_title(f"{query} [search]"))
        await self._iter_posts(scrape_item, self.api.search(query))

    @error_handling_wrapper
    async def user(self, scrape_item: ScrapeItem, username: str) -> None:
        data, pages = await aio.peek_next(self.api.user_posts(username))
        name = data["user"]["name"]
        scrape_item.setup_as_profile(self.create_title(f"@{name}"))
        await self._iter_posts(scrape_item, pages)

    async def _iter_posts(self, scrape_item: ScrapeItem, pages: AsyncIterable[dict[str, Any]]):
        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg, aio.maybe_aclosing(pages):
            async for data in pages:
                for post in data["posts"]:
                    web_url = self.PRIMARY_URL / "post" / str(post["content"]["id"])
                    tg.create_task(self._post_task(scrape_item.create_child(web_url), post))
                    scrape_item.add_children()
                    await sleep()

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, post_id: str) -> None:
        post = await self.api.post(post_id)
        await self._post(scrape_item, post)

    @error_handling_wrapper
    async def _post(self, scrape_item: ScrapeItem, post: dict[str, Any]) -> None:
        content: dict[str, Any] = post["content"]
        data: dict[str, Any] = post["data"]
        post_id = str(content["id"])

        scrape_item.uploaded_at = date = self.parse_date(post["publishedAt"], "%B %Y")
        title = self.create_separate_post_title(content["title"], post_id, date)
        scrape_item.setup_as_album(self.create_title(title), album_id=post_id)

        match ctype := content["type"]:
            case "gallery":
                files = data["urls"]
            case "video":
                files = [data["videos"]["mp4"]]
            case "image":
                files: list[str] = [data["url"]]
            case _:
                raise ScrapeError(422, f"Unknown post type = {ctype}")

        async with aio.non_cancelling_taskgroup() as tg:
            tg.create_task(self.write_metadata(scrape_item, f"post_{post_id}", post))
            for url in files:
                tg.create_task(self.direct_file(scrape_item, self.parse_url(url)))

    _post_task = auto_task_id(_post)


def _random_id(length: int = 8) -> str:
    import secrets
    import string

    return "".join(secrets.choice(string.digits) for _ in range(length))


class NsfwXXXAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://nsfw.xxx/api")
    BASE_QUERY: ClassVar[dict[str, list[int]]] = {"nsfw[]": [0, 1, 2, 3, 4]}

    def __post_init__(self) -> None:
        self.__http_ctx__.headers["Referer"] = str(self.PRIMARY_URL / "post" / _random_id())

    @disk_cached_method("service-token-passport", ttl=86_400 * 3)
    async def refresh_token(self) -> str:
        url = self.ENTRYPOINT / "v2/auth/refresh-passport-token"
        async with self.request(url):
            ...

        return self.client.get_cookies(self.PRIMARY_URL)["service-token-passport"]

    async def post(self, post_id: str) -> dict[str, Any]:
        url = (self.ENTRYPOINT / "v1/post" / post_id).with_query(self.BASE_QUERY)
        resp = await self.request_json(url, headers={"Referer": str(self.PRIMARY_URL / "post" / post_id)})
        return resp["data"]["post"]

    def user_posts(self, username: str) -> AsyncGenerator[dict[str, Any]]:
        return self.pager(self.ENTRYPOINT / "v1/user" / username)

    def search(self, query: str) -> AsyncGenerator[dict[str, Any]]:
        return self.pager((self.ENTRYPOINT / "v1/search").with_query(q=query))

    def subreddit(self, subreddit: str) -> AsyncGenerator[dict[str, Any]]:
        return self.pager(self.ENTRYPOINT / "v1/source/r" / subreddit)

    def category(self, subreddit: str) -> AsyncGenerator[dict[str, Any]]:
        return self.pager(self.ENTRYPOINT / "v1/category" / subreddit)

    async def pager(self, url: AbsoluteHttpURL) -> AsyncGenerator[dict[str, Any]]:
        query = {"page": 1, "types[]": ["image", "video", "gallery"]} | self.BASE_QUERY
        url = url.update_query(query)
        while True:
            resp = await self.request_json(url)
            yield resp["data"]
            next_page: str | None = resp["meta"].get("nextPage")
            if not next_page:
                break

            url = self.parse_url(next_page)
