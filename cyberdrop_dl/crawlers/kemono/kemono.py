from __future__ import annotations

import re
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import NoExtensionError, ScrapeError
from cyberdrop_dl.utils import unique
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from cyberdrop_dl.config.crawlers import KemonoConfig
    from cyberdrop_dl.crawlers.kemono.api import KemonoAPI
    from cyberdrop_dl.crawlers.kemono.models import File, Post, UserPost
    from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem


_find_http_urls = re.compile(r"(?:http(?!.*\.\.)[^ ]*?)(?=($|\n|\r\n|\r|\s|\"|\[/URL]|']\[|]\[|\[/img]|</|'))").finditer


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
            await self.api.creator.gather_ads(service, creator_id)

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


def _thumbnail_to_src(og_url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    url = og_url.with_path(og_url.path.replace("/thumbnails/", "/").replace("/thumbnail/", "/"))
    if name := og_url.query.get("f"):
        return url.with_query(f=name)
    return url
