from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem

_BASE_QUERY = "nsfw[]=0&nsfw[]=1&nsfw[]=2&nsfw[]=3&nsfw[]=4"
_TYPES_QUERY = "types[]=image&types[]=video&types[]=gallery"


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

    @property
    def separate_posts(self) -> bool:
        return True

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["post", post_id]:
                return await self.post(scrape_item, post_id)
            case ["user", user]:
                return await self.user(scrape_item, user)
            case ["r", subreddit]:
                return await self.subreddit(scrape_item, subreddit)
            case ["category", name]:
                return await self.category(scrape_item, name)
            case ["search"] if query := scrape_item.url.query.get("q"):
                return await self.search(scrape_item, query)
            case _:
                raise ValueError

    async def subreddit(self, scrape_item: ScrapeItem, subreddit: str) -> None:
        api_url = self.PRIMARY_URL / "api/v1/source/r" / subreddit
        await self._collection(scrape_item, api_url)

    async def category(self, scrape_item: ScrapeItem, name: str) -> None:
        api_url = self.PRIMARY_URL / "api/v1/category" / name
        await self._collection(scrape_item, api_url)

    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        api_url = (self.PRIMARY_URL / "api/v1/search").with_query(q=query)
        await self._collection(scrape_item, api_url, query)

    async def user(self, scrape_item: ScrapeItem, username: str) -> None:
        api_url = self.PRIMARY_URL / "api/v1/user" / username
        await self._collection(scrape_item, api_url, f"@{username}")

    @error_handling_wrapper
    async def _collection(self, scrape_item: ScrapeItem, api_url: AbsoluteHttpURL, name: str | None = None) -> None:
        title: str = ""
        type_ = api_url.parts[3]
        async for data in self._api_pager(api_url):
            if not title:
                name: str = name or data[type_]["name"].removeprefix("/r/")
                title = name if type_ == "source" else f"{name} [{type_}]"
                scrape_item.setup_as_profile(self.create_title(title))

            for post in data["posts"]:
                web_url = self.PRIMARY_URL / "post" / str(post["content"]["id"])
                new_scrape_item = scrape_item.create_child(web_url)
                self.create_task(self._post(new_scrape_item, post))
                scrape_item.add_children()

    async def _api_pager(self, url: AbsoluteHttpURL) -> AsyncGenerator[dict[str, Any]]:
        api_url = url.update_query(page=1).update_query(_TYPES_QUERY).update_query(_BASE_QUERY)
        while True:
            resp = await self.request_json(api_url)
            yield resp["data"]
            next: str | None = resp["meta"].get("nextPage")
            if not next:
                break

            api_url = self.parse_url(next)

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, post_id: str) -> None:
        api_url = (self.PRIMARY_URL / "api/v1/post" / post_id).with_query(_BASE_QUERY)
        post = (await self.request_json(api_url))["data"]["post"]
        await self._post(scrape_item, post)

    @error_handling_wrapper
    async def _post(self, scrape_item: ScrapeItem, post: dict[str, Any]) -> None:
        content: dict[str, Any] = post["content"]
        data: dict[str, Any] = post["data"]
        type_: str = content["type"]

        scrape_item.possible_datetime = date = self.parse_date(post["publishedAt"])
        title = self.create_separate_post_title(content["title"], str(content["id"]), date)
        scrape_item.setup_as_album(self.create_title(title), album_id=str(content["id"]))

        if type_ == "gallery":
            files = data["urls"]
        elif type_ == "video":
            files = [data["videos"]["mp4"]]
        elif type_ == "image":
            files: list[str] = [data["url"]]
        else:
            raise ScrapeError(422, f"Unknown post type = {type_}")

        for url in files:
            src = self.parse_url(url)
            await self.direct_file(scrape_item, src)
