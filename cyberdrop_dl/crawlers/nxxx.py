from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import open_graph
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class NsfwXXXCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Post": "/post/<id>",
        "User": "/user/<username>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://nsfw.xxx")
    DOMAIN: ClassVar[str] = "nsfw.xxx"
    FOLDER_DOMAIN: ClassVar[str] = DOMAIN

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["post", post_id]:
                return await self.post(scrape_item, post_id)
            case ["user", user]:
                return await self.user(scrape_item, user)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def user(self, scrape_item: ScrapeItem, username: str) -> None:
        api_url = (self.PRIMARY_URL / "api/v1/user" / username).with_query(
            "types[]=image&types[]=video&types[]=gallery&nsfw[]=0&nsfw[]=1&nsfw[]=2&nsfw[]=3&nsfw[]=4"
        )
        title: str = ""
        while True:
            resp = await self.request_json(api_url)
            data = resp["data"]
            if not title:
                name: str = data["user"]["name"]
                title = self.create_title(f"{name} (@{username})")
                scrape_item.setup_as_profile(title)

            for post in data["posts"]:
                self.create_task(self._api_post(scrape_item.copy(), post))
                scrape_item.add_children()

            next: str | None = resp["meta"].get("nextPage")
            if not next:
                break

            api_url = self.parse_url(next)

    @error_handling_wrapper
    async def _api_post(self, scrape_item: ScrapeItem, post: dict[str, Any]):
        content: dict[str, Any] = post["content"]
        post_id: str = str(content["id"])
        title: str = content["title"]
        post_data: dict[str, Any] = post["data"]
        scrape_item.url = self.PRIMARY_URL / "post" / post_id
        url = post_data["videos"]["mp4"] if content["type"] == "video" else post_data["url"]
        src = self.parse_url(url)
        filename = self.create_custom_filename(title, src.suffix, file_id=post_id)
        await self.handle_file(src, scrape_item, src.name, src.suffix, custom_filename=filename)

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, post_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        og = open_graph.parse(soup)
        src = self.parse_url(og.video or og.image)
        filename = self.create_custom_filename(og.title, src.suffix, file_id=post_id)
        await self.handle_file(src, scrape_item, src.name, src.suffix, custom_filename=filename)
