# ruff : noqa: N815

from __future__ import annotations

import dataclasses
import itertools
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.url_objects import ScrapeItem


_CDN = AbsoluteHttpURL("https://cdn.cara.app")


class CaraCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Post": "/post/<id>",
        "User": "/<username>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://cara.app")
    DOMAIN: ClassVar[str] = PRIMARY_URL.host
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date:%Y-%m-%d} - {id}"

    @property
    @override
    def separate_posts(self) -> bool:
        return True

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["post", user_name]:
                return await self.post(scrape_item, user_name)
            case [user_name]:
                return await self.user(scrape_item, user_name)
            case _:
                raise ValueError

    def __post_init__(self) -> None:
        self.api: CaraAPI = CaraAPI.from_crawler(self)

    @error_handling_wrapper
    async def user(self, scrape_item: ScrapeItem, username: str) -> None:
        scrape_item.setup_as_profile("")
        async for posts in self.api.user_posts(username):
            for post in posts:
                url = self.PRIMARY_URL / "post" / post.id
                new_item = scrape_item.create_child(url)
                self.create_task(self._post(new_item, post))
                scrape_item.add_children()

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, post_id: str) -> None:
        post = await self.api.post(post_id)
        await self._post(scrape_item, post)

    @error_handling_wrapper
    async def _post(self, scrape_item: ScrapeItem, post: Post) -> None:
        scrape_item.setup_as_post(self.create_title(f"@{post.user.slug}"))
        scrape_item.uploaded_at = date = int(self.parse_iso_date(post.createdAt))
        post_title = self.create_separate_post_title(post.title, post.id, date)
        scrape_item.append_folders(post_title)
        self.create_eager_task(self.write_metadata(scrape_item, f"post {post.id}", post))

        for image in post.images:
            if image.order < 0:
                continue
            self.create_eager_task(self._image(scrape_item, image))
            scrape_item.add_children()

    async def _image(self, scrape_item: ScrapeItem, image: Image) -> None:
        src = _CDN / image.src
        with self.catch_errors(src):
            filename, ext = self.get_filename_and_ext(src.name)
            await self.handle_file(
                src,
                scrape_item,
                src.name,
                ext,
                custom_filename=filename,
                metadata=image,
            )


@dataclasses.dataclass(slots=True, order=True)
class User:
    slug: str
    name: str


@dataclasses.dataclass(slots=True, order=True)
class Image:
    order: int
    src: str
    isEmbed: bool
    width: int | None
    height: int | None
    embedType: str | None
    mediaSrc: str | None


@dataclasses.dataclass(slots=True, order=True)
class Post:
    id: str
    createdAt: str
    user: User
    content: str
    title: str
    images: tuple[Image, ...]

    @classmethod
    def parse(cls, post: dict[str, Any]) -> Self:
        return deserialize(
            cls,
            post,
            user=deserialize(User, post),
            images=tuple(deserialize(Image, img) for img in post["images"]),
        )


class CaraAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://cara.app/api")

    async def post(self, post_id: str) -> Post:
        api_url = self.ENTRYPOINT / "posts" / post_id
        resp: dict[str, Any] = await self.request_json(api_url)
        return Post.parse(resp["data"])

    def user_posts(self, user: str) -> AsyncGenerator[map[Post]]:
        url = (self.ENTRYPOINT / "posts/getAllByUser").with_query(slug=user)
        return self._pager(url)

    async def _pager(self, api_url: AbsoluteHttpURL) -> AsyncGenerator[map[Post]]:
        step_size = 50
        for skip in itertools.count(0, step_size):
            resp = await self.request_json(api_url.update_query(take=step_size, skip=skip))
            data = resp.get("data", ())
            n_posts = len(data)
            yield map(Post.parse, data)
            if n_posts < step_size:
                break
