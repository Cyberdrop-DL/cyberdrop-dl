from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


_API_URL = AbsoluteHttpURL("https://api.fxtwitter.com")


class TwitterCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Tweet": "/<handle>/status/<tweet_id>",
    }
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("twitter.com",)
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://x.com")
    DOMAIN: ClassVar[str] = "twitter"
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date:%Y-%m-%d} - {id}"

    @property
    def separate_posts(self) -> bool:
        return True

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_user, "status", _]:
                return await self.tweet(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def tweet(self, scrape_item: ScrapeItem) -> None:
        url = _API_URL / scrape_item.url.path.removeprefix("/")
        tweet: dict[str, Any] = (await self.request_json(url))["tweet"]
        scrape_item.possible_datetime = tweet["created_timestamp"]
        name = tweet["author"]["screen_name"]
        post_title = self.create_separate_post_title(None, tweet["id"], scrape_item.possible_datetime)
        scrape_item.setup_as_profile(self.create_title(f"@{name}"))
        scrape_item.add_to_parent_title(post_title)

        await self.write_metadata(scrape_item, tweet["id"], tweet)

        for media in tweet["media"]["all"]:
            if media["type"] == "video":
                media = max(media["formats"], key=lambda f: f.get("bitrate", 0))

            source = self.parse_url(media["url"])
            new_item = scrape_item.create_child(source)
            self.handle_external_links(new_item, reset=False)
            scrape_item.add_children()
