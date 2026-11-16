from __future__ import annotations

import itertools
import json
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import Deduper, css
from cyberdrop_dl.utils.dataclass import Deserializer, deserialize, struct
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.url_objects import ScrapeItem


class ImgCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Post": "/p/<slug>",
        "User posts": "/u/<username>",
        "Direct files": "",
    }
    DOMAIN: ClassVar[str] = "imgchest"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://imgchest.com")

    def __post_init__(self) -> None:
        self.api: ImgChestAPI = ImgChestAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if self.is_subdomain(scrape_item.url):
            await self.direct_file(scrape_item)
            return

        match scrape_item.url.parts[1:]:
            case ["p", slug]:
                await self.post(scrape_item, slug)
            case ["u", username]:
                await self.user(scrape_item, username)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def user(self, scrape_item: ScrapeItem, username: str) -> None:
        scrape_item.setup_as_album(self.create_title(f"{username} [user]"))
        sleep = aio.periodic_sleep(10)
        async with aio.maybe_aclosing(self.api.user_posts(username, sort=scrape_item.url.query.get("sort"))) as posts:
            async for post in posts:
                new_item = scrape_item.create_child(self.PRIMARY_URL / "p" / post)
                self.create_task(self.run(new_item))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, post_slug: str) -> None:
        post, downloaded = await aio.gather(self.api.post(post_slug), self.get_completed_by_album(post_slug))
        scrape_item.setup_as_album(self.create_title(post.title or f"post {post.slug}", post.slug), album_id=post.slug)
        if post.created_at:
            scrape_item.uploaded_at = self.parse_iso_date(post.created_at)

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg, aio.maybe_aclosing(self.api.files(post)) as files:
            tg.create_task(self.write_metadata(scrape_item, f"post_{post.slug}", post))
            async for file in files:
                if file.link in downloaded:
                    continue
                tg.create_task(self.file(scrape_item, file))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, file: File) -> None:
        filename, ext = self.get_filename_and_ext(file.link.name, mime_type=file.type)
        await self.handle_file(
            file.link,
            scrape_item,
            file.link.name,
            ext,
            thumbnail=file.thumbnail,
            metadata=file,
            custom_filename=filename,
        )


@struct
class Post:
    slug: str
    title: str | None
    nsfw: int
    files_total: int
    files: tuple[File, ...]
    tags: tuple[str, ...]
    created_at: str | None = None
    description: str | None = None


@struct
class File:
    id: str
    thumbnail: AbsoluteHttpURL
    link: AbsoluteHttpURL
    mp4: int
    type: str
    size: int
    nsfw: bool

    parse = classmethod(Deserializer(converters=dict.fromkeys(("thumbnail", "link"), ImgCrawler.parse_url)))


class ImgChestAPI(API):
    async def post(self, slug: str) -> Post:
        soup = await self.request_soup(self.PRIMARY_URL / "p" / slug)
        data = css.select(soup, "#app", "data-page")
        post = json.loads(data)["props"]["post"]
        return deserialize(
            Post,
            post,
            files=tuple(map(File.parse, post.get("files", ()))),
            tags=[tag["name"] for tag in post.get("tags", ())],
        )

    async def files(self, post: Post) -> AsyncGenerator[File]:
        unique = Deduper.by_attr("id").filter

        for file in unique(post.files):
            yield file

        if len(post.files) >= post.files_total:
            return

        url = self.PRIMARY_URL / "p" / post.slug / "files"
        for page in itertools.count(2):
            data = await self.request_json(url.update_query(page=page))
            for file in unique(map(File.parse, data["files"])):
                yield file

            if data["page"] * 40 >= data["total"]:
                break

    async def user_posts(self, username: str, sort: str | None = "new") -> AsyncGenerator[str]:
        url = (self.PRIMARY_URL / "api/posts").with_query(
            sort=sort or "new",
            tag="",
            q="",
            username=username,
            nsfw="true",
        )

        for page in itertools.count(1):
            resp = await self.request_json(url.update_query(page=page))
            posts = [g["slug"] for g in resp["data"]]
            del resp
            for post in posts:
                yield post
            if len(posts) < 24:
                break
