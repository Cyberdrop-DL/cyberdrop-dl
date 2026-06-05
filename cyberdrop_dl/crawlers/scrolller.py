from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.url_objects import ScrapeItem


_GRAPHQL_API_ENTRYPOINT = AbsoluteHttpURL("https://api.scrolller.com/api/v2/graphql")


class ScrolllerCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Subreddit": "/r/<subreddit>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://scrolller.com")
    DOMAIN: ClassVar[str] = "scrolller"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["r", subreddit]:
                return await self.subreddit(scrape_item, subreddit)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def subreddit(self, scrape_item: ScrapeItem, subreddit: str) -> None:
        title = self.create_title(subreddit)
        scrape_item.setup_as_album(title)

        async for items in self._api_pagination(subreddit):
            for item in items:
                src = _get_source(item)
                if not src:
                    continue

                self.create_task(self.direct_file(scrape_item, self.parse_url(src)))
                scrape_item.add_children()

    async def _api_pagination(self, subreddit: str) -> AsyncGenerator[list[dict[str, Any]]]:
        variables: dict[str, Any] = {"url": f"/r/{subreddit}", "filter": None, "hostsDown": None}
        request_body = {"query": _SUBREDDIT_GRAPHQL_QUERY, "variables": variables}
        iterator = None
        iterations = 0

        while True:
            variables["iterator"] = iterator
            data: dict[str, dict[str, Any]] = (
                await self.request_json(
                    _GRAPHQL_API_ENTRYPOINT,
                    method="POST",
                    data=json.dumps(request_body),
                    headers={"Content-Type": "application/json"},
                )
            )["data"]
            items: list[dict[str, Any]] = data["getSubreddit"]["children"]["items"] if data else []
            if not items:
                break

            yield items

            prev_iterator = iterator
            iterator = data["getSubreddit"]["children"]["iterator"]
            if iterator is None or iterator == prev_iterator or iterations > 0:
                break

            iterations += 1


def _get_source(item: dict[str, Any]) -> str | None:
    for src in item["mediaSources"]:
        if ".webp" not in src["url"]:
            return src["url"]

    return None


_SUBREDDIT_GRAPHQL_QUERY = """
    query SubredditQuery(
        $url: String!
        $filter: SubredditPostFilter
        $iterator: String
    ) {
        getSubreddit(url: $url) {
            title
            children(
                limit: 10000
                iterator: $iterator
                filter: $filter
                disabledHosts: null
            ) {
                iterator
                items {
                    title
                    mediaSources {
                        url
                    }
                    blurredMediaSources {
                        url
                    }
                }
            }
        }
    }
"""
