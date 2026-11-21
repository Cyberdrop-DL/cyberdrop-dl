from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, TypedDict, override

from cyberdrop_dl import aio
from cyberdrop_dl.constants import FileExt
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths, URLConfig
from cyberdrop_dl.network.http import HTTPConfig
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import dates
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.url_objects import ScrapeItem


@HTTPConfig(rate_limit=(3, 1))
@URLConfig(allow_empty_path=True)
class WhiteKittenCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Post": ("/posts/<post_id>",),
        "Search": "/?q=<query>",
    }
    DOMAIN: ClassVar[str] = "whitekitten"
    FOLDER_DOMAIN: ClassVar[str] = "WhiteKitten"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://whitekitten.art")
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date:%Y-%m-%d} - {id}"

    def __post_init__(self) -> None:
        self.api: WhiteKittenAPI = WhiteKittenAPI.from_crawler(self)

    @property
    @override
    def separate_posts(self) -> bool:
        return True

    @override
    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["posts", post_id]:
                await self.post(scrape_item, post_id)
            case [""] | [] if query := scrape_item.url.query.get("q"):
                await self.search(scrape_item, query)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        scrape_item.setup_as_album(self.create_title(f"{query} [search]"))
        sleep = aio.periodic_sleep(10)
        async with (
            aio.non_cancelling_taskgroup() as tg,
            aio.maybe_aclosing(self.api.search(query)) as post_pages,
        ):
            async for posts in post_pages:
                for post_id in posts:
                    url = self.PRIMARY_URL / f"posts/{post_id}"
                    tg.create_task(self.run(scrape_item.create_child(url)))
                    scrape_item.add_children()
                    await sleep()

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, post_id: str) -> None:
        post = await self.api.post(post_id)
        scrape_item.upload_date = date = dates.parse_iso(post["createdAt"])
        title = self.create_separate_post_title(None, post_id, date)
        scrape_item.setup_as_album(self.create_title(title, post_id), album_id=post_id)

        files: list[File] = post.pop("files") or []  # pyright: ignore[reportAssignmentType]
        async with aio.non_cancelling_taskgroup() as tg:
            tg.create_task(self.write_metadata(scrape_item, f"post {post['id']}", post))
            for file in files:
                src = self.parse_url(file["mediaUrl"])
                _, ext = self.get_filename_and_ext(src.name, mime_type=file.get("mimeType"))
                if ext == ".avif" and (png := file.get("pngUrl")):
                    src, ext = self.parse_url(png), ".png"

                idx = file["fileOrder"] + 1
                tg.create_task(
                    self.handle_file(
                        src,
                        scrape_item,
                        src.name,
                        ext,
                        custom_filename=self.create_custom_filename(f"{idx:03} - {src.name}", ext),
                        metadata=file,
                        thumbnail=file.get("thumbnailUrl") if ext in FileExt.VIDEO else None,
                    )
                )


class Post(TypedDict):
    id: int
    createdAt: str
    files: list[File]
    description: str | None


class File(TypedDict):
    id: int
    fileOrder: int
    mimeType: str
    fileSize: int
    mediaUrl: str
    pngUrl: str | None
    thumbnailUrl: str | None


class WhiteKittenAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://whitekitten.art/api")

    async def post(self, post_id: str) -> Post:
        url = self.ENTRYPOINT / "posts" / post_id
        resp = await self.request_json(url.update_query(maxRating="explicit"))
        return resp["data"]["post"]

    async def search(self, query: str) -> AsyncGenerator[list[int]]:
        url = (self.ENTRYPOINT / "posts").update_query(q=query, maxRating="explicit")
        while True:
            data = (await self.request_json(url))["data"]
            yield [p["id"] for p in data["posts"] if p["fileCount"] > 0]
            cursor = data.get("cursor")
            if not cursor:
                break
            url = url.update_query(cursor=cursor)
