from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.crawlers.twitter.api import FXTwitterAPI
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.crawlers.twitter.models import Post, Tweet
    from cyberdrop_dl.url_objects import ScrapeItem


class TwitterCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Tweet": "/<user_handle>/status/<snowflake_id>",
    }
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("twitter.com",)
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://x.com")
    DOMAIN: ClassVar[str] = "twitter"
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date:%Y-%m-%d} - {id}"
    _RATE_LIMIT: ClassVar[RateLimit] = 3, 1  # Actual limit is 1000 req/min (~ 16.7 req/s) per IP

    def __post_init__(self) -> None:
        self.api: FXTwitterAPI = FXTwitterAPI.from_crawler(self)

    @property
    def separate_posts(self) -> bool:
        return True

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_user, "status", status_id]:
                await self.tweet(scrape_item, status_id)
            case [user, "media"]:
                await self.user_media(scrape_item, user)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def tweet(self, scrape_item: ScrapeItem, status_id: str) -> None:
        tweet = await self.api.tweet(status_id, entire_thread=True)
        self._tweet(scrape_item, tweet)

    @error_handling_wrapper
    def _tweet(self, scrape_item: ScrapeItem, tweet: Tweet) -> None:
        scrape_item.uploaded_at = tweet.status.created_timestamp
        post_title = self.create_separate_post_title(None, tweet.status.id, scrape_item.uploaded_at)
        scrape_item.setup_as_profile(self.create_title(f"@{tweet.author['screen_name']}"))
        scrape_item.append_folders(post_title)
        self.create_eager_task(self.write_metadata(scrape_item, tweet.status.id, tweet))

        for post in tweet.thread:
            if post.type == "status":
                self._post(scrape_item, post)

    def _post(self, scrape_item: ScrapeItem, post: Post) -> None:
        for media, is_embed in post.media:
            source = self.parse_url(media.best_src)
            new_item = scrape_item.create_child(source)
            self.handle_external_links(new_item, reset=is_embed)
            scrape_item.add_children()

    @error_handling_wrapper
    async def user_media(self, scrape_item: ScrapeItem, user: str) -> None:
        scrape_item.setup_as_profile("")
        with self._cursor_ctx(scrape_item.url):
            async for tweets in self.api.user.media(user):
                for tweet in tweets:
                    new_item = scrape_item.create_child(self.parse_url(tweet.status.url))
                    self._tweet(new_item, tweet)
                    scrape_item.add_children()

    @contextlib.contextmanager
    def _cursor_ctx(self, url: AbsoluteHttpURL, cursor: str | None = None) -> Generator[None]:
        self.api.cursor = cursor or url.query.get("cursor")
        try:
            yield
        finally:
            if cursor := self.api.cursor:
                self.log.info(
                    "Use cursor '%s' as a query param to resume scraping from the same point. ex: %s",
                    cursor,
                    url.update_query(cursor=cursor),
                )
