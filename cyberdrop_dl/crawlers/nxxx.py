from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem

_BASE_QUERY = "nsfw[]=1&nsfw[]=2&nsfw[]=3&nsfw[]=4"
_TYPES_QUERY = "types[]=image&types[]=video&types[]=gallery"


class NsfwXXXCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Post": "/post/<id>",
        "User": "/user/<username>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://nsfw.xxx")
    DOMAIN: ClassVar[str] = "nsfw.xxx"
    FOLDER_DOMAIN: ClassVar[str] = DOMAIN
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date:%Y-%m-%d} - {title} [{id}]"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["post", post_id]:
                return await self.post(scrape_item, post_id)
            case ["user", user]:
                return await self.user(scrape_item, user)
            case ["r", subreddit]:
                return await self.subreddit(scrape_item, subreddit)
            case _:
                raise ValueError

    @property
    def separate_posts(self) -> bool:
        return True

    @error_handling_wrapper
    async def subreddit(self, scrape_item: ScrapeItem, subreddit: str) -> None:
        api_url = self.PRIMARY_URL / "api/v1/source/r" / subreddit
        title: str = ""

        async for data in self._api_pager(api_url):
            if not title:
                name: str = data["source"]["name"].removeprefix("/r/")
                title = self.create_title(name)
                scrape_item.setup_as_forum(title)

            for post in data["posts"]:
                self.create_task(self._post(scrape_item.copy(), post))
                scrape_item.add_children()

    @error_handling_wrapper
    async def user(self, scrape_item: ScrapeItem, username: str) -> None:
        api_url = self.PRIMARY_URL / "api/v1/user" / username
        title: str = ""

        async for data in self._api_pager(api_url):
            if not title:
                name: str = data["user"]["name"]
                title = self.create_title(f"{name} (@{username})")
                scrape_item.setup_as_profile(title)

            for post in data["posts"]:
                self.create_task(self._post(scrape_item.copy(), post))
                scrape_item.add_children()

    async def _api_pager(self, url: AbsoluteHttpURL) -> AsyncGenerator[dict[str, Any]]:
        api_url = url.with_query(_BASE_QUERY).update_query(_TYPES_QUERY)
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
        post_id: str = str(content["id"])
        data: dict[str, Any] = post["data"]
        type_: str = content["type"]

        scrape_item.url = self.PRIMARY_URL / "post" / post_id
        scrape_item.possible_datetime = date = self.parse_date(post["publishedAt"])
        title = self.create_separate_post_title(content["title"], post_id, date)
        scrape_item.setup_as_album(title)

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
