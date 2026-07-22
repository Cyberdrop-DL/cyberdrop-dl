from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers.crawler import API
from cyberdrop_dl.crawlers.twitter.models import Status
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.dataclass import deserialize


class FXTwitterAPI(API):
    # https://docs.fxembed.com/api/twitter/
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.fxtwitter.com/2")

    async def status(self, status_id: str) -> Status:
        url = self.ENTRYPOINT / "status" / status_id
        resp = await self.request_json(url)
        return deserialize(Status, resp["status"])
