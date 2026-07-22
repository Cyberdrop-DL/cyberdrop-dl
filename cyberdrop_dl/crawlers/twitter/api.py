# https://docs.fxembed.com/api/twitter/
# https://github.com/FxEmbed/FxEmbed
from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import API
from cyberdrop_dl.crawlers.twitter.models import Tweet
from cyberdrop_dl.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class FXTwitterAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.fxtwitter.com/2")
    cursor: ClassVar[ContextVar[str | None]] = ContextVar("cursor")

    def __post_init__(self) -> None:
        self.user: UserEndpoint = UserEndpoint(self)

    async def tweet(self, status_id: str) -> Tweet:
        url = (self.ENTRYPOINT / "status" / status_id).with_query(about_account=1)
        resp = await self.request_json(url)
        return Tweet.model_validate(resp)

    async def thread(self, status_id: str) -> map[Tweet]:
        url = self.ENTRYPOINT / "thread" / status_id
        resp = await self.request_json(url)
        # filter out deleted tweets ( "type" == "tombstone")
        tweets = (t for t in resp["thread"] if t["type"] == "status")
        return map(Tweet.model_validate, tweets)

    async def pager(self, url: AbsoluteHttpURL) -> AsyncGenerator[map[Tweet]]:
        url = url.update_query(count=100)
        if cursor := self.cursor.get():
            url = url.update_query(cursor=cursor)
        while True:
            resp = await self.request_json(url)
            yield map(Tweet.model_validate, resp["results"])
            self.cursor.set(cursor := resp["cursor"].get("bottom"))
            if not cursor:
                break
            url = url.update_query(cursor=cursor)


class UserEndpoint:
    def __init__(self, api: FXTwitterAPI) -> None:
        self.api: FXTwitterAPI = api

    def media(self, user: str) -> AsyncGenerator[map[Tweet]]:
        url = self.api.ENTRYPOINT / "profile" / user / "media"
        return self.api.pager(url)
