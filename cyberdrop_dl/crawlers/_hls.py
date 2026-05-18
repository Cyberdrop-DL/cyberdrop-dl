from __future__ import annotations

import asyncio
import dataclasses
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal

from cyberdrop_dl.utils import m3u8

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    import aiohttp

    from cyberdrop_dl.url_objects import AbsoluteHttpURL


class HLSParser(ABC):
    """Class to fetch and parse HTTP live streams

    For multi variant m3u8, the best resolution will be automatically selected"""

    @abstractmethod
    async def request_text(
        self,
        url: AbsoluteHttpURL,
        /,
        method: Literal["GET"] = "GET",
        headers: Mapping[str, str] | None = None,
    ) -> str: ...

    async def request_m3u8(
        self,
        url: AbsoluteHttpURL,
        /,
        headers: Mapping[str, str] | None = None,
        *,
        only: Iterable[str] = (),
        exclude: Iterable[str] = ("vp09",),
    ) -> tuple[m3u8.Rendition, m3u8.RenditionDetails | None]:
        m3u8_obj = await self._request_m3u8(url, headers)
        if m3u8_obj.is_variant:
            rendition = m3u8.select_best_rendition(m3u8_obj, only=only, exclude=exclude)
            return await self._resolve_rendition(rendition, headers)
        m3u8_obj.media_type = "video"
        return m3u8.Rendition(m3u8_obj, None, None), None

    async def _resolve_rendition(
        self,
        rendition: m3u8.RenditionDetails,
        /,
        headers: Mapping[str, str] | None = None,
    ):

        async def resolve(url: AbsoluteHttpURL | None, media_type: Literal["video", "audio", "subtitle"]):
            if not url:
                return None
            return await self._request_m3u8(url, headers, media_type)

        video, audio, subs = await asyncio.gather(
            *(
                resolve(url, name)
                for name, url in zip(
                    ("video", "audio", "subtitle"),
                    rendition.urls,
                    strict=True,
                )
            )
        )
        assert video
        return m3u8.Rendition(video, audio, subs), rendition

    async def _request_m3u8(
        self,
        url: AbsoluteHttpURL,
        /,
        headers: Mapping[str, str] | None = None,
        media_type: Literal["video", "audio", "subtitle"] | None = None,
    ) -> m3u8.M3U8:
        content = await self.request_text(url, headers=headers)
        return m3u8.M3U8(content, url.parent, media_type)


@dataclasses.dataclass(slots=True)
class SimpleHLSParser(HLSParser):
    """A simple parser that does not depend on the manager.

    DO NOT USE. This is only for testing"""

    _session: aiohttp.ClientSession

    async def request_text(
        self,
        url: AbsoluteHttpURL,
        /,
        method: Literal["GET"] = "GET",
        headers: Mapping[str, str] | None = None,
    ) -> str:
        async with self._session.get(url, headers=headers) as resp:
            return await resp.text()
