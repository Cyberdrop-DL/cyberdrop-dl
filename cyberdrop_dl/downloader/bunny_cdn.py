from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import logging
import random
from contextvars import ContextVar
from typing import TYPE_CHECKING, cast, override

from cyberdrop_dl import aio
from cyberdrop_dl.downloader.http import Downloader

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem
    from cyberdrop_dl.utils.m3u8 import Rendition

logger = logging.getLogger(__name__)

_playback_time = ContextVar[int]("_playback_time", default=0)
_playback_url: ContextVar[AbsoluteHttpURL] = ContextVar("_playback_url")


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class PingData:
    url: AbsoluteHttpURL
    headers: dict[str, str]
    secret: str
    context_id: str
    resolution: int = 1080
    period: int = 2


def _sign_url(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    return url.update_query(hash=hashlib.md5("_".join(url.query.values()).encode(), usedforsecurity=False).hexdigest())


class BunnyCDNDownloader(Downloader):
    async def _ping_playback(self, ping: PingData) -> None:
        current_time = _playback_time.get() + ping.period
        _playback_time.set(current_time)
        ping_url = _sign_url(
            ping.url.update_query(
                time=current_time + round(random.random(), 6),
                paused="false",
                resolution=ping.resolution,
            )
        )

        try:
            async with self.client.http_client.raw_request(ping_url, headers=ping.headers):
                ...
        except Exception:
            logger.exception("BunnyCDN ping for %s failed", _playback_url.get())

    @override
    async def _hls(self, media_item: MediaItem, rendition: Rendition) -> None:
        try:
            ping = cast("PingData", media_item.extra_info[media_item.domain]["ping_data"])
        except LookupError:
            background_ping = contextlib.nullcontext()
        else:
            background_ping = aio.backgroud_task(lambda: self._ping_playback(ping), period=ping.period)
            _playback_url.set(media_item.real_url)

        async with background_ping:
            await super()._hls(media_item, rendition)
