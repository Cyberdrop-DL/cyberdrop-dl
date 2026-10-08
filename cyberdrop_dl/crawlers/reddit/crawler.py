from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.crawlers.reddit.api import ArcticShiftAPI, SearchQuery
from cyberdrop_dl.filepath import get_filename_and_ext
from cyberdrop_dl.mediaprops import Subtitle
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import css, parse_url, unique
from cyberdrop_dl.utils._url import remove_query_params
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from cyberdrop_dl.config.crawlers import RedditConfig
    from cyberdrop_dl.crawlers.reddit.types import Submission
    from cyberdrop_dl.url_objects import ScrapeItem


@Crawler.db_path_builder("url")
class RedditImagesCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "preview.redd.it", "external-preview.redd.it", "i.redd.it"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Image": "i.redd.it/<id>.>ext>"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://i.redd.it")
    DOMAIN: ClassVar[str] = "i.redd.it"
    FOLDER_DOMAIN: ClassVar[str] = "Reddit"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = "i.reddituploads.com", "i.redditmedia.com"

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        if "external" not in url.host:
            url = remove_query_params(url, keep=("s",))
        if url.host == "preview.redd.it":
            return url.with_host(cls.PRIMARY_URL.host)
        return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_]:
                await self.image(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        if not scrape_item.url.suffix:
            ext = await self.sniff_ext(scrape_item.url)
            with scrape_item.track_changes:
                scrape_item.url = scrape_item.url.with_suffix(ext)
        await self.direct_file(scrape_item)


@Crawler.db_path_builder("url")
class RedditVideoCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Video": "v.redd.it/<video_id>"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://v.redd.it")
    DOMAIN: ClassVar[str] = "v.redd.it"
    FOLDER_DOMAIN: ClassVar[str] = "Reddit"

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = remove_query_params(super().transform_url(url), keep=("s",))
        match url.parts[1:]:
            case [_, _]:
                return url.parent.with_query(url.query)
            case _:
                return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [video_id]:
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        m3u8_url = self.PRIMARY_URL / video_id / "HLSPlaylist.m3u8"
        if await self.check_complete(m3u8_url):
            return

        m3u8, info = await self.request_m3u8_playlist(m3u8_url)
        filename = self.create_custom_filename(
            video_id,
            ext := ".mp4",
            resolution=info and info.resolution,
            video_codec=info and info.codecs.video,
            audio_codec=info and info.codecs.audio,
        )
        await self.handle_file(m3u8_url, scrape_item, video_id, ext, m3u8=m3u8, custom_filename=filename)
        self.handle_subs(scrape_item, filename, [Subtitle(m3u8_url.with_name("wh_ben_en.vtt"), lang_code="en")])


class RedditCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "User submissions": (
            "/u/<user>",
            "/u/<user>/submitted",
            "/user/<user>",
            "/user/<user>/submitted",
        ),
        "Subreddit:": "/r/<subreddit>",
        "Submission": (
            "/comments/<id>",
            "/r/<subreddit>/comments/<id>/...",
            "/user/<user>/comments/<id>/...",
        ),
        "Media": "/link/...",
        "Redirects": (
            "/gallery/<id>",
            "/r/<subreddit>/s/<share_id>",
            "/u/<user>/s/<share_id>",
            "/user/<user>/s/<share_id>",
        ),
    }
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{title} - {id}"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.reddit.com")
    DOMAIN: ClassVar[str] = "reddit"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = "www.old.reddit.com", "old.reddit.com"

    def __post_init__(self) -> None:
        self.api: ArcticShiftAPI = ArcticShiftAPI.from_crawler(self)

    @property
    @override
    def separate_posts(self) -> bool:
        return True

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["u" | "user", user] | ["u" | "user", user, "submitted"]:
                await self.user(scrape_item, user)
            case ["r", subreddit]:
                await self.subreddit(scrape_item, subreddit)
            case ["r" | "user" | "u", _, "comments", post_id, *_] | ["comments", post_id]:
                await self.submission(scrape_item, post_id)
            case ["gallery", _] | ["r" | "u" | "user", _, "s", _, *_]:
                await self.follow_redirect(scrape_item)
            case ["link", _, "video", video_id, *_]:
                with scrape_item.track_changes:
                    scrape_item.url = RedditVideoCrawler.PRIMARY_URL / video_id
                self.handle_embed(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def user(self, scrape_item: ScrapeItem, username: str) -> None:
        scrape_item.setup_as_profile(self.create_title(username))
        await self._iter_posts(
            scrape_item,
            self.api.posts_search(
                SearchQuery(
                    author=username,
                    after=self.config.filters.after,
                    before=self.config.filters.before,
                )
            ),
        )

    @error_handling_wrapper
    async def subreddit(self, scrape_item: ScrapeItem, subreddit: str) -> None:
        scrape_item.setup_as_profile(self.create_title(subreddit))
        await self._iter_posts(
            scrape_item,
            self.api.posts_search(
                SearchQuery(
                    subreddit=subreddit,
                    after=self.config.filters.after,
                    before=self.config.filters.before,
                )
            ),
        )

    async def _iter_posts(self, scrape_item: ScrapeItem, submissions: AsyncGenerator[Submission]) -> None:
        async with contextlib.aclosing(submissions) as posts:
            async for post in posts:
                new_item = scrape_item.create_child(self.parse_url(post["permalink"]))
                self.post(new_item, post)
                scrape_item.add_children()

    @error_handling_wrapper
    def post(self, scrape_item: ScrapeItem, post: Submission) -> None:
        scrape_item.uploaded_at = post["created_utc"]
        scrape_item.setup_as_post(
            self.create_title(self.create_separate_post_title(post["title"], post["id"], post["created_utc"]))
        )
        self.create_eager_task(self.write_metadata(scrape_item, post["id"], post))
        for url in unique(_extract_urls(post, self.config.crawlers.reddit)):
            if url.host == self.PRIMARY_URL.host:
                continue

            self.handle_embed(scrape_item.create_child(url))
            scrape_item.add_children()

    @error_handling_wrapper
    async def submission(self, scrape_item: ScrapeItem, post_id: str) -> None:
        post = await self.api.post(post_id)
        self.post(scrape_item, post)


def _extract_urls(post: Submission, config: RedditConfig) -> Generator[AbsoluteHttpURL]:
    if gallery := post.get("gallery_data"):
        metadata = post.get("media_metadata") or {}
        for item in gallery["items"]:
            media_id = item["media_id"]
            meta = metadata[media_id]
            if meta.get("status", "valid") != "valid":
                RedditCrawler.get_logger().warning("Invalid image (deleted?)\n%s\n%s", item, meta)
            try:
                mimetype = meta["m"]
            except LookupError:
                name = media_id
            else:
                name, _ = get_filename_and_ext(media_id, mime_type=mimetype)
            yield RedditImagesCrawler.PRIMARY_URL / name

    yield parse_url(post.get("url_overridden_by_dest") or post["url"])

    if config.content_urls and (content := post.get("selftext_html")):
        soup = css.soup(content, parse_only="a")
        yield from map(parse_url, css.iselect(soup, "a[href]", "href"))
