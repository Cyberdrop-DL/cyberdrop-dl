# https://docs.fxembed.com/api/twitter/
# https://github.com/FxEmbed/FxEmbed
from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, ClassVar, Final

from cyberdrop_dl import signature
from cyberdrop_dl.crawlers.crawler import API
from cyberdrop_dl.crawlers.twitter.models import Broadcast, Tweet
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping


class FXTwitterAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.fxtwitter.com/2")
    cursor: ClassVar[ContextVar[str | None]] = ContextVar("cursor")
    since: ClassVar[ContextVar[int | None]] = ContextVar("since")

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

    def search(self, query: str, feed: str = "latest") -> AsyncGenerator[map[Tweet]]:
        url = (self.ENTRYPOINT / "search").with_query(q=query, feed=feed)
        return self.pager(url)

    async def pager(self, url: AbsoluteHttpURL) -> AsyncGenerator[map[Tweet]]:
        url = url.update_query(count=100)
        if cursor := self.cursor.get():
            url = url.update_query(cursor=cursor)
        if since := self.since.get():
            url = url.update_query(since=since)

        while True:
            resp = await self.request_json(url)
            yield map(Tweet.model_validate, resp["results"])
            cursor = resp["cursor"].get("bottom")
            self.cursor.set(cursor)
            if not cursor or url.query.get("cursor") == cursor:
                break
            url = url.update_query(cursor=cursor)


class UserEndpoint:
    def __init__(self, api: FXTwitterAPI) -> None:
        self.api: FXTwitterAPI = api

    def media(self, user: str) -> AsyncGenerator[map[Tweet]]:
        url = self.api.ENTRYPOINT / "profile" / user / "media"
        return self.api.pager(url)

    def tweets(self, user: str) -> AsyncGenerator[map[Tweet]]:
        url = self.api.ENTRYPOINT / "profile" / user / "statuses"
        return self.api.pager(url)


class TwitterAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.x.com/1.1")
    auth_token: str = ""
    guess_token: str = ""

    def __post_init__(self) -> None:
        self.broadcast: BroadcastEndpoint = BroadcastEndpoint(self)

    async def activate(self) -> str:
        url = self.ENTRYPOINT / "guest/activate.json"
        return await self.request_json(url, data=b"")

    @signature.copy(API.request_json)
    async def request_json(self, *args, headers: Mapping[str, str] | None = None, **kwargs) -> Any:
        async with self.request(*args, headers=headers, **kwargs) as resp:
            return await resp.json(content_type=False)


class BroadcastEndpoint:
    ENDED: Final = "ENDED"

    def __init__(self, api: TwitterAPI) -> None:
        self.api: TwitterAPI = api

    async def __call__(self, broadcast_id: str) -> Broadcast:
        url = (self.api.ENTRYPOINT / "broadcasts/show.json").with_query(ids=broadcast_id)
        resp = await self.api.request_json(url)
        return self._parse(resp["broadcasts"][broadcast_id])

    async def event(self, event_id: str) -> Broadcast:
        url = self.api.ENTRYPOINT / "live_event/1" / event_id / "timeline.json"
        resp = await self.api.request_json(url)
        bds_entries: dict[str, dict[str, Any]] = resp["twitter_objects"]["broadcasts"]
        return self._parse(next(iter(bds_entries.values())))

    def _parse(self, bd: dict[str, Any]) -> Broadcast:
        if not bd:
            raise ScrapeError(404)
        state: str = bd.setdefault("state", self.ENDED)
        if state != self.ENDED:
            raise ScrapeError(422, f"{state} broadcasts are not supported")
        return Broadcast.model_validate(bd)

    async def stream(self, media_key: str) -> AbsoluteHttpURL:
        url = self.api.ENTRYPOINT / "live_video_stream/status" / media_key
        source = (await self.api.request_json(url))["source"]
        url = self.api.parse_url(source.get("noRedirectPlaybackUrl") or source["location"])
        if "geoblocked" in url.parts:
            raise ScrapeError(403, "Broadcast not available in this location")
        return url
