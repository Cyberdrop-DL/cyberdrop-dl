from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.crawlers.twitter.api import FXTwitterAPI
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.twitter.models import Post
    from cyberdrop_dl.url_objects import ScrapeItem


class TwitterCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Tweet": "/<user_handle>/status/<snowflake_id>",
    }
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("twitter.com",)
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://x.com")
    DOMAIN: ClassVar[str] = "twitter"
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date:%Y-%m-%d} - {id}"
    _RATE_LIMIT: ClassVar[RateLimit] = 3, 1  # Actual rate limit is 1000 reqs / min (16.7 reqs / s) per IP

    def __post_init__(self) -> None:
        self.api: FXTwitterAPI = FXTwitterAPI.from_crawler(self)

    @property
    def separate_posts(self) -> bool:
        return True

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_user, "status", status_id]:
                return await self.tweet(scrape_item, status_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def tweet(self, scrape_item: ScrapeItem, status_id: str) -> None:
        tweet = await self.api.tweet(status_id, entire_thread=True)
        scrape_item.uploaded_at = tweet.status.created_timestamp
        post_title = self.create_separate_post_title(None, status_id, scrape_item.uploaded_at)
        scrape_item.setup_as_profile(self.create_title(f"@{tweet.author.screen_name}"))
        scrape_item.append_folders(post_title)
        self.create_eager_task(self.write_metadata(scrape_item, status_id, tweet))

        for post in tweet.thread:
            self._post(scrape_item, post)

    def _post(self, scrape_item: ScrapeItem, post: Post) -> None:
        videos = (video.best_format for video in post.media.videos)
        external = [post.media.external] if post.media.external else []
        for media in itertools.chain(post.media.photos, videos, external):
            source = self.parse_url(media.url)
            new_item = scrape_item.create_child(source)
            self.handle_external_links(new_item, reset=False)
            scrape_item.add_children()
