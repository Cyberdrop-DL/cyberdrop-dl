# https://github.com/ArthurHeitmann/arctic_shift/tree/master/api
from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Final, Literal

from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.constants import CDL_USER_AGENT
from cyberdrop_dl.crawlers.crawler import API
from cyberdrop_dl.crawlers.reddit.types import Author, Submission, Subreddit
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.dataclass import DictDataclass

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import AsyncGenerator


def _parse_post(post: Submission) -> Submission:
    post["author"] = Author.parse(post)
    post["subreddit"] = Subreddit.parse(post)
    return post


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class SearchQuery:
    author: str | None = None
    subreddit: str | None = None
    author_flair_text: str | None = None
    after: dt.date | None = None
    before: dt.date | None = None
    sort: Literal["desc", "asc"] = "desc"
    limit: int = 100

    def __post_init__(self) -> None:
        assert 0 < self.limit < 500

    __iter__ = DictDataclass.__iter__

    def __json__(self) -> dict[str, str]:
        return {k: str(v) for k, v in self if v}


@HTTPConfig(rate_limit=(1, 2), headers={"User-Agent": CDL_USER_AGENT})
class ArcticShiftAPI(API):
    ENTRYPOINT: Final = AbsoluteHttpURL("https://arctic-shift.photon-reddit.com/api")

    async def posts(self, *ids: str) -> map[Submission]:
        assert 0 < len(ids) < 500
        url = (self.ENTRYPOINT / "posts/ids").with_query(ids=",".join(ids), md2html="true")
        resp = await self.request_json(url)
        return map(_parse_post, resp["data"])

    async def post(self, id: str) -> Submission:  # noqa: A002
        posts = await self.posts(id)
        try:
            return next(posts)
        except StopIteration:
            raise ScrapeError(404) from None

    def posts_search(self, query: SearchQuery) -> AsyncGenerator[Submission]:
        return self.search("posts/search", query)

    async def search(self, path: str, query: SearchQuery) -> AsyncGenerator[Submission]:
        url = (self.ENTRYPOINT / path.removeprefix("/")).with_query(query.__json__()).update_query(md2html="true")
        while True:
            resp = await self.request_json(url)
            for post in resp["data"]:
                yield _parse_post(post)

            if len(resp["data"]) < query.limit:
                break

            url = url.update_query(
                {
                    "before" if query.sort == "desc" else "after": resp["data"][-1]["created_utc"],
                }
            )
