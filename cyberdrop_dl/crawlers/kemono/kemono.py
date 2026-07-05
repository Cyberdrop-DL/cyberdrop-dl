from __future__ import annotations

import re
from abc import abstractmethod
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import NoExtensionError, ScrapeError
from cyberdrop_dl.utils import parse_url, unique
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from cyberdrop_dl.config.crawlers import KemonoConfig
    from cyberdrop_dl.crawlers.kemono.api import KemonoAPI
    from cyberdrop_dl.crawlers.kemono.models import File, Post, UserPost
    from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem


_find_http_urls = re.compile(r"(?:http(?!.*\.\.)[^ ]*?)(?=($|\n|\r\n|\r|\s|\"|\[/URL]|']\[|]\[|\[/img]|</|'))").finditer


class KemonoBaseCrawler(Crawler, is_abc=True):
    __kemono_api__: ClassVar[type[KemonoAPI]]
    __kemono_cdn__: ClassVar[AbsoluteHttpURL]

    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Creator": "/<service>/user/<user_id>",
        "Favorites": (
            r"/favorites?type=post|artist",
            r"/account/favorites/posts|artists",
        ),
        "Search": "/search?q=...",
        "Post": "/<service>/user/<user_id>/post/<post_id>",
        "Direct links": (
            "/data/...",
            "/thumbnail/...",
        ),
    }
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date} - {title}"

    @property
    @abstractmethod
    def __kemono_config__(self) -> KemonoConfig: ...

    def __init_subclass__(cls, **kwargs: Any) -> None:
        assert cls.__kemono_api__
        assert cls.__kemono_cdn__
        return super().__init_subclass__(**kwargs)

    def __post_init__(self) -> None:
        self.api: KemonoAPI = self.__kemono_api__.from_crawler(self)

    async def __async_post_init__(self) -> None:
        with self.catch_errors(self.PRIMARY_URL), self.disable_on_error("Unable to get creators"):
            _ = await self.api.creators()

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [service, "user", creator_id, "post", post_id]:
                return await self.post(scrape_item, service, creator_id, post_id)
            case [service, "user", creator_id]:
                return await self.creator(scrape_item, service, creator_id)
            case ["favorites"] if (type_ := scrape_item.url.query.get("type")) in ("post", "artist", None):
                return await self.favorites(scrape_item, type_ or "artist")
            case ["account", "favorites", slug] if (type_ := slug.removesuffix("s")) in ("post", "artist"):
                return await self.favorites(scrape_item, type_)
            case ["posts"] if search_query := scrape_item.url.query.get("q"):
                return await self.search(scrape_item, search_query)
            case ["thumbnail" | "thumbnails" | "data", _, *_]:
                return await self._direct_file(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, search_query: str) -> None:
        title = self.create_title(f"{search_query} [search]")
        scrape_item.setup_as_profile(title)
        async for posts in self.api.search(scrape_item.url.query):
            await self.__iter_user_posts(scrape_item, posts)

    @error_handling_wrapper
    async def creator(self, scrape_item: ScrapeItem, service: str, creator_id: str) -> None:
        scrape_item.setup_as_profile("")

        async for posts in self.api.creator.posts(service, creator_id, scrape_item.url.query):
            await self.__iter_user_posts(scrape_item, posts)

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, service: str, creator_id: str, post_id: str) -> None:
        post = await self.api.post(service, creator_id, post_id)
        await self._user_post(scrape_item, post)

    @error_handling_wrapper
    async def favorites(self, scrape_item: ScrapeItem, type_: Literal["post", "artist"]) -> None:
        session_cookie = self.cookies.get("session")
        if not session_cookie:
            msg = "No session cookie found, cannot scrape favorites"
            raise ScrapeError(401, msg)

        title = f"My favorite {type_}s"
        scrape_item.setup_as_profile(self.create_title(title))
        try:
            async for favorites in await self.api.account.favorites(type_):
                for fav in favorites:
                    url = self.PRIMARY_URL / fav.web_path_qs
                    new_scrape_item = scrape_item.create_child(url)
                    self.create_task(self.run(new_scrape_item))
        finally:
            self.update_cookies({"session": ""})

    @error_handling_wrapper
    async def _direct_file(self, scrape_item: ScrapeItem, url: AbsoluteHttpURL | None = None) -> None:
        scrape_item.url = _thumbnail_to_src(scrape_item.url)
        link = _thumbnail_to_src(url or scrape_item.url)
        checksum = Path(link.name).stem
        if await self.check_complete_by_hash(link, "sha256", checksum):
            return

        name = link.query.get("f") or link.name
        try:
            filename, ext = self.get_filename_and_ext(name)
        except NoExtensionError:
            # Some patreon URLs have another URL as the filename:
            # ex: https://kemono.su/data/7a...27ad7e40bd.jpg?f=https://www.patreon.com/media-u/Z0F..00672794_
            filename, ext = self.get_filename_and_ext(link.name)

        await self.handle_file(link, scrape_item, name, ext, custom_filename=filename)

    @error_handling_wrapper
    async def _user_post(self, scrape_item: ScrapeItem, post: UserPost) -> None:
        self.__check_for_ads(post)
        user_name = (await self.api.creators())[post.user]
        title = self.create_title(user_name, post.user_id)
        scrape_item.setup_as_album(title, album_id=post.user_id)
        scrape_item.uploaded_at = post.timestamp
        post_title = self.create_separate_post_title(post.title, post.id, post.timestamp)
        scrape_item.append_folders(post_title)
        self.create_task(self.write_metadata(scrape_item, f"post_{post.id}", post))
        self._extract_post_files(scrape_item, post)
        self._extract_urls_from_post_content(scrape_item, post)

    def _extract_post_files(self, scrape_item: ScrapeItem, post: Post) -> None:
        for url in unique(self.__prepare_files(post)):
            self.create_task(self._direct_file(scrape_item, url))
            scrape_item.add_children()

        if self.__kemono_config__.embed and post.embed:
            embed_url = self.parse_url(post.embed.url)
            new_scrape_item = scrape_item.create_child(embed_url)
            self.handle_external_links(new_scrape_item)
            scrape_item.add_children()

    def _extract_urls_from_post_content(self, scrape_item: ScrapeItem, post: Post) -> None:
        if not post.content or self.__kemono_config__.content_urls:
            return

        for url in _parse_content_urls(post, self.DOMAIN):
            new_scrape_item = scrape_item.create_child(url)
            self.handle_external_links(new_scrape_item)
            scrape_item.add_children()

    def __check_for_ads(self, post: Post) -> None:
        if _has_ads(post):
            self.log.warning(f"post #{post.id} contains advertisements")

    def __prepare_files(self, post: Post) -> Generator[AbsoluteHttpURL]:
        if not post.has_full:
            self.log.warning("Post #%s has not been fully imported. Some (or all) files may be missing", post.id)

        def all_files() -> Generator[File]:
            if self.__kemono_config__.file and post.file:
                yield post.file
            if self.__kemono_config__.attachments:
                yield from post.attachments

        for file in all_files():
            if file.deferred:
                self.log.warning("Skipping file '%s' in post #%s [incomplete import]", file.name, post.id)
                continue

            assert file.path
            url = self.__kemono_cdn__ / f"data{file.path}"
            yield url.with_query(f=file.name or url.name)

    async def __iter_user_posts(self, scrape_item: ScrapeItem, posts: Iterable[UserPost]) -> None:
        for post in posts:
            self.__check_for_ads(post)
            new_item = scrape_item.create_child(self.parse_url(post.web_path_qs))
            if not self.__kemono_config__.content_urls or post.content is not None:
                await self._user_post(new_item, post)
            else:
                self.create_task(self.run(new_item))
            scrape_item.add_children()


def _thumbnail_to_src(og_url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    url = og_url.with_path(og_url.path.replace("/thumbnails/", "/").replace("/thumbnail/", "/"))
    if name := og_url.query.get("f"):
        return url.with_query(f=name)
    return url


def _has_ads(post: Post) -> bool:
    if post.content and "#ad" in post.content:
        return True

    ci_tags = {tag.casefold() for tag in post.tags}
    return bool(ci_tags.intersection({"ad", "#ad", "ads", "#ads"}))


def _parse_content_urls(post: Post, host: str | None = None) -> Generator[AbsoluteHttpURL]:
    if not post.content:
        return
    for link in _extract_urls(post.content):
        try:
            url = parse_url(link, trim=False)
        except Exception:  # noqa: BLE001
            pass
        else:
            if not host or host not in url.host:
                yield url


def _extract_urls(content: str) -> Generator[str]:
    seen: set[str] = set()
    for match in _find_http_urls(content):
        if (url := match.group().replace(".md.", ".")) not in seen:
            seen.add(url)
            yield url
