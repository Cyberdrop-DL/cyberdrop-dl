from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import API
from cyberdrop_dl.crawlers.twitter.models import Tweet
from cyberdrop_dl.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

_CURSOR: ContextVar[str | None] = ContextVar("_CURSOR")


class FXTwitterAPI(API):
    # https://docs.fxembed.com/api/twitter/
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.fxtwitter.com/2")

    def __post_init__(self) -> None:
        self.user: UserEndpoint = UserEndpoint(self)

    @property
    def cursor(self) -> str | None:
        return _CURSOR.get(None)

    @cursor.setter
    def cursor(self, value: str | None) -> None:
        _CURSOR.set(value)

    async def tweet(self, status_id: str, *, entire_thread: bool = False) -> Tweet:
        endpoint = "thread" if entire_thread else "status"
        url = (self.ENTRYPOINT / endpoint / status_id).with_query(about_account=1)
        resp = await self.request_json(url)
        return Tweet.model_validate(resp)

    async def pager(self, url: AbsoluteHttpURL) -> AsyncGenerator[map[Tweet]]:
        url = url.update_query(count=100)
        if cursor := self.cursor:
            url = url.update_query(cursor=cursor)
        while True:
            resp = await self.request_json(url)
            yield map(Tweet.model_validate, resp["results"])
            _CURSOR.set(cursor := resp["cursor"].get("bottom"))
            if not cursor:
                break
            url = url.update_query(cursor=cursor)


class UserEndpoint:
    def __init__(self, api: FXTwitterAPI) -> None:
        self.api: FXTwitterAPI = api

    def media(self, user: str) -> AsyncGenerator[map[Tweet]]:
        url = self.api.ENTRYPOINT / "profile" / user / "media"
        return self.api.pager(url)
