from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.crawlers.twitter.api import FXTwitterAPI
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.config.crawlers import TwitterConfig
    from cyberdrop_dl.crawlers.twitter.models import Tweet
    from cyberdrop_dl.url_objects import ScrapeItem


class TwitterCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Tweet/Thread": "/<user_handle>/status/<status_id>",
        "User media": "/<user_handle>/media",
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

    @property
    def __config__(self) -> TwitterConfig:
        return self.config.crawlers.twitter

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_user, "status", status_id]:
                fn = self.thread if self.__config__.thread else self.tweet
                await fn(scrape_item, status_id)
            case [user, "media"]:
                await self.user_media(scrape_item, user)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def tweet(self, scrape_item: ScrapeItem, status_id: str) -> None:
        tweet = await self.api.tweet(status_id)
        self._tweet(scrape_item, tweet)

    @error_handling_wrapper
    async def thread(self, scrape_item: ScrapeItem, status_id: str) -> None:
        tweet, *replies = await self.api.thread(status_id)
        self.__init_thread(scrape_item, tweet)
        self.__tweet(scrape_item, tweet)
        for tweet in replies:
            new_item = scrape_item.create_child(self.parse_url(tweet.url))
            self.__tweet(new_item, tweet)
            scrape_item.add_children()

    def _tweet(self, scrape_item: ScrapeItem, tweet: Tweet) -> None:
        self.__init_thread(scrape_item, tweet)
        self.__tweet(scrape_item, tweet)

    def __init_thread(self, scrape_item: ScrapeItem, tweet: Tweet) -> None:
        scrape_item.setup_as_album(self.create_title(f"@{tweet.author['screen_name']}"))

    @error_handling_wrapper
    def __tweet(self, scrape_item: ScrapeItem, tweet: Tweet) -> None:
        scrape_item.uploaded_at = tweet.created_timestamp
        post_title = self.create_separate_post_title(None, tweet.id, scrape_item.uploaded_at)
        scrape_item.append_folders(post_title)
        self.create_eager_task(self.write_metadata(scrape_item, tweet.id, tweet))

        for media, is_embed in tweet.media:
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
                    new_item = scrape_item.create_child(self.parse_url(tweet.url))
                    self._tweet(new_item, tweet)
                    scrape_item.add_children()

    @contextlib.contextmanager
    def _cursor_ctx(self, url: AbsoluteHttpURL, cursor: str | None = None) -> Generator[None]:
        init_cursor = cursor or url.query.get("cursor")
        self.api.cursor.set(init_cursor)
        try:
            yield
        finally:
            cursor = self.api.cursor.get()
            if cursor and cursor != init_cursor:
                self.log.info(
                    "Use cursor '%s' as a query param to resume scraping from the same point. ex: %s",
                    cursor,
                    url.update_query(cursor=cursor),
                )
