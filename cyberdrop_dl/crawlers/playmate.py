from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class PlaymateCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/embed/<video_id>",
            "/watch/<video_id>",
        ),
    }
    DOMAIN: ClassVar[str] = "playmate"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://playmate.to")

    def __post_init__(self) -> None:
        self.api: PlaymateAPI = PlaymateAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["watch" | "embed", video_id]:
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        embed_url = self.PRIMARY_URL / "embed" / video_id
        if await self.check_complete(embed_url):
            return

        video = await self.api.video(video_id)
        m3u8, info = await self.request_m3u8_playlist(video.m3u8)
        await self.handle_file(
            embed_url,
            scrape_item,
            video.title,
            ext := ".mp4",
            m3u8=m3u8,
            custom_filename=self.create_custom_filename(video.title, ext, file_id=video_id, resolution=info.resolution),
            thumbnail=video.thumb,
        )


@dataclasses.dataclass(slots=True, frozen=True)
class Video:
    id: str
    title: str
    m3u8: AbsoluteHttpURL
    thumb: AbsoluteHttpURL


class PlaymateAPI(API):
    async def video(self, video_id: str) -> Video:
        stream, meta = await aio.gather(
            self.request_json(self.PRIMARY_URL / "api/s", method="POST", json={"d": "web", "c": video_id}),
            self.request_json((self.PRIMARY_URL / "api/video-meta").with_query(filecode=video_id)),
            fail_fast=False,
        )
        return Video(
            id=video_id,
            title=meta.get("title") or video_id,
            m3u8=self.parse_url(stream["sx"]),
            thumb=self.parse_url(stream["ix"]),
        )
