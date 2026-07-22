from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers.crawler import API
from cyberdrop_dl.crawlers.twitter.models import Tweet
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.dataclass import deserialize


class FXTwitterAPI(API):
    # https://docs.fxembed.com/api/twitter/
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.fxtwitter.com/2")

    async def tweet(self, status_id: str, *, entire_thread: bool = False) -> Tweet:
        endpoint = "thread" if entire_thread else "status"
        url = (self.ENTRYPOINT / endpoint / status_id).with_query(about_account=1)
        resp = await self.request_json(url)
        return deserialize(Tweet, resp)
