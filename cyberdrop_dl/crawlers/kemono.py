from __future__ import annotations

import datetime  # noqa: TC003
import itertools
import re
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, NamedTuple, override

from pydantic import BeforeValidator, Field

from cyberdrop_dl import signature
from cyberdrop_dl.cache import cached_method
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import NoExtensionError, ScrapeError
from cyberdrop_dl.models import DeferredModel
from cyberdrop_dl.models.validators import falsy_as, falsy_as_none
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import unique
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator, Iterable

    from cyberdrop_dl.config.crawlers import KemonoConfig
    from cyberdrop_dl.url_objects import ScrapeItem


_DEFAULT_PAGE_SIZE = 50
_DISCORD_CHANNEL_PAGE_SIZE = 150

_find_http_urls = re.compile(r"(?:http(?!.*\.\.)[^ ]*?)(?=($|\n|\r\n|\r|\s|\"|\[/URL]|']\[|]\[|\[/img]|</|'))").finditer


class User(NamedTuple):
    service: str
    id: str


class File(NamedTuple):
    path: str
    name: str | None = None  # Sometimes present
    server: str | None = None  # Sometimes present in attachments


class Embed(NamedTuple):
    url: str
    subject: str
    description: str


class Post(DeferredModel):
    id: str
    content: str = ""
    file: Annotated[File | None, BeforeValidator(falsy_as_none)] = None
    attachments: tuple[File, ...] = ()
    published: datetime.datetime | None = None
    added: datetime.datetime | None = None
    edited: datetime.datetime | None = None
    timestamp: int | None = None
    tags: Annotated[tuple[str, ...], BeforeValidator(lambda x: falsy_as(x, ()))] = ()
    embed: Annotated[Embed | None, BeforeValidator(falsy_as_none)] = None

    @override
    def model_post_init(self, *_: object) -> None:
        if date := self.published or self.added:
            self.timestamp = int(date.timestamp())

    @property
    def all_files(self) -> Generator[File]:
        if self.file:
            yield self.file
        yield from self.attachments


class UserPost(Post):
    service: str
    user_id: str = Field(validation_alias="user")
    title: str

    @property
    def user(self) -> User:
        return User(self.service, self.user_id)

    @property
    def web_path_qs(self) -> str:
        return f"{self.service}/user/{self.user_id}/post/{self.id}"


class KemonoBaseCrawler(Crawler, is_abc=True):
    __kemono_api__: ClassVar[KemonoAPI]

    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Model": "/<service>/user/<user_id>",
        "Favorites": (
            r"/favorites?type=post\|artist",
            r"/account/favorites/posts\|artists",
        ),
        "Search": "/search?q=...",
        "Individual Post": "/<service>/user/<user_id>/post/<post_id>",
        "Direct links": (
            "/data/...",
            "/thumbnail/...",
        ),
    }
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date} - {title}"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        Crawler._assert_fields_overrides(cls, "SERVICES")

    def __post_init__(self) -> None:
        self.api: KemonoAPI = self.__kemono_api__.from_crawler(self)

    @property
    def _my_config(self) -> KemonoConfig:
        return getattr(self.config.crawlers, self.DOMAIN)

    @property
    def ignore_content(self) -> bool:
        return self._my_config.ignore_post_content

    @property
    def ignore_ads(self) -> bool:
        return self._my_config.ignore_ads

    async def __async_post_init__(self) -> None:
        with self.catch_errors(self.PRIMARY_URL), self.disable_on_error("Unable to get creators"):
            _ = await self.api.creators()

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [service, "user", creator_id, "post", post_id]:
                return await self.post(scrape_item, service, creator_id, post_id)
            case [service, "user", creator_id]:
                return await self.creator(scrape_item, service, creator_id)
            case ["favorites"] if (type_ := scrape_item.url.query.get("type")) in {"post", "artist", None}:
                type_ = type_ or "artist"
                return await self.favorites(scrape_item, type_)
            case ["account", "favorites", slug] if (type_ := slug.removesuffix("s")) in {"post", "artist"}:
                return await self.favorites(scrape_item, type_)
            case ["posts"] if search_query := scrape_item.url.query.get("q"):
                return await self.search(scrape_item, search_query)
            case ["thumbnail" | "thumbnails" | "data", _, *_]:
                return await self.handle_direct_link(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        title = self.create_title(f"{query} [search]")
        scrape_item.setup_as_profile(title)
        async for posts in self.api.search(query=query):
            await self.__iter_user_posts(scrape_item, posts)

    @error_handling_wrapper
    async def creator(self, scrape_item: ScrapeItem, service: str, creator_id: str) -> None:
        scrape_item.setup_as_profile("")
        if self.ignore_ads:
            self.log.info(f"filtering out all ad posts for {creator_id}. This could take a while")
            await self.api.creator.filter_ads(service, creator_id)

        async for posts in self.api.creator.posts(service, creator_id):
            await self.__iter_user_posts(scrape_item, posts)

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, service: str, creator_id: str, post_id: str) -> None:
        post = await self.api.post(service, creator_id, post_id)
        await self._handle_user_post(scrape_item, post)

    @error_handling_wrapper
    async def favorites(self, scrape_item: ScrapeItem, type_: str) -> None:
        session_cookie = self.cookies.get("session")
        if not session_cookie:
            msg = "No session cookie found, cannot scrape favorites"
            raise ScrapeError(401, msg)

        title = f"My favorite {type_}s"
        scrape_item.setup_as_profile(self.create_title(title))
        self.update_cookies({"session": session_cookie})
        resp = await self.api.account.favorites(type_)
        self.update_cookies({"session": ""})

        for item in resp:
            url = self.PRIMARY_URL / item["service"] / "user" / (item.get("user") or item["name"])
            if type_ == "post":
                url = url / "post" / item["id"]

            new_scrape_item = scrape_item.create_child(url)
            self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def handle_direct_link(self, scrape_item: ScrapeItem, url: AbsoluteHttpURL | None = None) -> None:
        scrape_item.url = _thumbnail_to_src(scrape_item.url)
        link = _thumbnail_to_src(url or scrape_item.url)
        hash_value = Path(link.name).stem
        if await self.check_complete_by_hash(link, "sha256", hash_value):
            return

        try:
            filename, ext = self.get_filename_and_ext(link.query.get("f") or link.name)
        except NoExtensionError:
            # Some patreon URLs have another URL as the filename:
            # ex: https://kemono.su/data/7a...27ad7e40bd.jpg?f=https://www.patreon.com/media-u/Z0F..00672794_
            filename, ext = self.get_filename_and_ext(link.name)

        await self.handle_file(link, scrape_item, link.name, ext, custom_filename=filename)

    async def _handle_user_post(self, scrape_item: ScrapeItem, post: UserPost) -> None:
        user_name = (await self.api.creators())[post.user]
        title = self.create_title(user_name, post.user_id)
        scrape_item.setup_as_album(title, album_id=post.user_id)
        scrape_item.uploaded_at = post.timestamp
        post_title = self.create_separate_post_title(post.title, post.id, post.timestamp)
        scrape_item.append_folders(post_title)
        self.__handle_post(scrape_item, post)

    def _handle_post_content(self, scrape_item: ScrapeItem, post: Post) -> None:
        """Gets links out of content in post and sends them to a new crawler."""
        if not post.content or self.ignore_content:
            return

        for link in self.__parse_content_urls(post):
            new_scrape_item = scrape_item.create_child(link)
            self.handle_external_links(new_scrape_item)
            scrape_item.add_children()

    def __parse_content_urls(self, post: Post) -> Generator[AbsoluteHttpURL]:
        seen: set[str] = set()
        for match in _find_http_urls(post.content):
            if (link := match.group().replace(".md.", ".")) not in seen:
                seen.add(link)
                try:
                    url = self.parse_url(link)
                except Exception:  # noqa: BLE001
                    pass
                else:
                    if self.DOMAIN not in url.host:
                        yield url

    def __has_ads(self, post: Post) -> bool:
        msg = f"skipping post #{post.id} (contains #advertisements)"
        if "#ad" in post.content or post.id in self.api.posts_w_ads:
            self.log.info(msg)
            return True

        ci_tags = {tag.casefold() for tag in post.tags}
        if ci_tags.intersection({"ad", "#ad", "ads", "#ads"}):
            self.log.info(msg)
            return True

        return False

    def __handle_post(self, scrape_item: ScrapeItem, post: Post) -> None:
        if self.ignore_ads and self.__has_ads(post):
            return

        self.create_task(self.write_metadata(scrape_item, f"post_{post.id}", post))

        files = (self.__make_file_url(file) for file in post.all_files)
        for url in unique(files):
            self.create_task(self.handle_direct_link(scrape_item, url))
            scrape_item.add_children()

        if post.embed:
            embed_url = self.parse_url(post.embed.url)
            new_scrape_item = scrape_item.create_child(embed_url)
            self.handle_external_links(new_scrape_item)
            scrape_item.add_children()

        self._handle_post_content(scrape_item, post)

    def __make_file_url(self, file: File) -> AbsoluteHttpURL:
        path = file.path
        url = self.parse_url(f"/data{path}")
        return url.with_query(f=file.name or url.name)

    async def __iter_user_posts(self, scrape_item: ScrapeItem, posts: Iterable[UserPost]) -> None:
        for post in posts:
            if self.ignore_ads and self.__has_ads(post):
                continue
            post_web_url = self.parse_url(post.web_path_qs)
            new_scrape_item = scrape_item.create_child(post_web_url)
            await self._handle_user_post(new_scrape_item, post)
            scrape_item.add_children()


class KemonoAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pawchive.pw/api/v1")

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        assert cls.ENTRYPOINT

    def __post_init__(self) -> None:
        self.posts_w_ads: list[str] = []
        self.post: PostEndpoint = PostEndpoint(self)
        self.creator: CreatorEndpoint = CreatorEndpoint(self)
        self.account: AccountEndpoint = AccountEndpoint(self)

    @override
    @signature.copy(API.request_json)
    async def request_json(self, *args, **kwargs) -> Any:
        async with self.request(*args, **kwargs) as resp:
            return await resp.json(encoding="utf-8", content_type=False)

    @cached_method(ttl=3600)
    async def creators(self) -> dict[User, str]:
        url = self.ENTRYPOINT / "creators"
        resp: list[dict[str, Any]] = await self.request_json(url)
        return {User(u["service"], u["id"]): u["name"] for u in resp}

    async def search(
        self, offset: int = 0, query: str | None = None, tags: str | None = None
    ) -> AsyncGenerator[map[UserPost]]:
        url = self.ENTRYPOINT / "posts"
        async for posts in self.pager(url.update_query(q=query or "", o=offset, tag=tags or "")):
            yield map(UserPost.model_validate, posts)

    async def search_hash(self, file_hash: str):
        url = self.ENTRYPOINT / "search_hash" / file_hash
        return await self.request_json(url)

    async def pager(
        self,
        url: AbsoluteHttpURL,
        step_size: int = 50,
        key: str | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]]]:
        for offset in itertools.count(int(url.query.get("o") or 0), step_size):
            data = await self.request_json(url.update_query(o=offset))
            if key is not None:
                data = data[key]
            if not data:
                break
            yield data
            if len(data) < step_size:
                break


class KemonoAPIEndpoint:
    api: KemonoAPI

    def __init__(self, api: KemonoAPI) -> None:
        self.api = api

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"


class AccountEndpoint(KemonoAPIEndpoint):
    async def favorites(self, type: str):  # noqa: A002
        endpoint = self.api.ENTRYPOINT / "account/favorites"
        return await self.api.request_json(endpoint.update_query(type=type))


class CreatorEndpoint(KemonoAPIEndpoint):
    async def announcements(self, service: str, creator_id: str):
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "announcements"
        return await self.api.request_json(url)

    async def dms(self, service: str, creator_id: str):
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "dms"
        return await self.api.request_json(url)

    async def fancards(self, service: str, creator_id: str):
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "fancards"
        return await self.api.request_json(url)

    async def profile(self, service: str, creator_id: str):
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "profile"
        return await self.api.request_json(url)

    async def links(self, service: str, creator_id: str):
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "links"
        return await self.api.request_json(url)

    async def tags(self, service: str, creator_id: str):
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "tags"
        return await self.api.request_json(url)

    async def posts(
        self, service: str, creator_id: str, offset: int = 0, query: str | None = None, tags: str | None = None
    ) -> AsyncGenerator[map[UserPost]]:
        endpoint = self.api.ENTRYPOINT / service / "user" / creator_id / "posts"
        _params = {"o": offset, "tag": tags, "q": query}
        async for posts in self.api.pager(endpoint):
            yield map(UserPost.model_validate, posts)

    async def filter_ads(self, service: str, creator_id: str) -> None:
        endpoint = self.api.ENTRYPOINT / service / "user" / creator_id / "posts"
        async for posts in self.api.pager(endpoint):
            self.api.posts_w_ads.extend(p["id"] for p in posts)


class PostEndpoint(KemonoAPIEndpoint):
    async def __call__(self, service: str, creator_id: str, post_id: str) -> UserPost:
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "post" / post_id
        resp = await self.api.request_json(url)
        return UserPost.model_validate(resp["post"])

    async def comments(self, service: str, creator_id: str, post_id: str):
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "post" / post_id / "comments"
        return await self.api.request_json(url)

    async def revisions(self, service: str, creator_id: str, post_id: str):
        url = self.api.ENTRYPOINT / service / "user" / creator_id / "post" / post_id / "revisions"
        return await self.api.request_json(url)


def _thumbnail_to_src(og_url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    url = og_url.with_path(og_url.path.replace("/thumbnails/", "/").replace("/thumbnail/", "/"))
    if name := og_url.query.get("f"):
        return url.with_query(f=name)
    return url
