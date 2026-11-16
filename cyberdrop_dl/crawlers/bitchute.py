from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, override

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.dataclass import deserialize, struct
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.url_objects import ScrapeItem


class BitChuteCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/video/<video_id>",
            "/embed/<video_id>",
        ),
        "Channel": "/channel/<channel_id>",
    }
    DOMAIN: ClassVar[str] = "bitchute"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.bitchute.com")
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("old.bitchute.com",)

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["embed", video_id]:
                return cls.PRIMARY_URL / "video" / video_id
            case _:
                return url

    def __post_init__(self) -> None:
        self.api: BitChuteAPI = BitChuteAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video", video_id]:
                await self.video(scrape_item, video_id)
            case ["channel", channel_id]:
                await self.channel(scrape_item, channel_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def channel(self, scrape_item: ScrapeItem, channel_id: str) -> None:
        channel = await self.api.channel(channel_id)
        scrape_item.setup_as_profile(self.create_title(channel["channel_name"], channel_id))
        sleep = aio.periodic_sleep(10)
        async with (
            aio.non_cancelling_taskgroup() as tg,
            aio.maybe_aclosing(self.api.channel_videos(channel_id)) as videos,
        ):
            tg.create_task(self.write_metadata(scrape_item, f"channel_{channel_id}", channel))
            async for video in videos:
                new_item = scrape_item.create_child(self.PRIMARY_URL / "video" / video.id)
                tg.create_task(self._video_task(new_item, video))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def _video_task(self, scrape_item: ScrapeItem, video: Video) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        if video.state_id == "live":
            raise ScrapeError.live_stream()

        src = await self.api.video_media(video.id)
        await self._video(scrape_item, video, src)

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        video, src = await aio.gather(self.api.video(video_id), self.api.video_media(video_id), fail_fast=False)
        await self._video(scrape_item, video, src)

    async def _video(self, scrape_item: ScrapeItem, video: Video, src: AbsoluteHttpURL) -> None:
        if video.state_id == "live":
            raise ScrapeError.live_stream()

        scrape_item.uploaded_at = self.parse_iso_date(video.date_published)
        m3u8 = info = None
        if src.suffix == ".m3u8":
            m3u8, info = await self.request_m3u8(src)

        await self.handle_file(
            src,
            scrape_item,
            video.name,
            ext := ".mp4",
            m3u8=m3u8,
            custom_filename=self.create_custom_filename(
                video.name, ext, file_id=video.id, resolution=info and info.resolution
            ),
            thumbnail=video.thumbnail_url,
            metadata=video,
        )


@struct
class Video:
    id: str
    name: str
    description: str
    date_published: str
    thumbnail_url: str
    state_id: str

    @classmethod
    def parse(cls, video: dict[str, Any]) -> Self:
        return deserialize(cls, video, id=video["video_id"], name=video["video_name"])


class BitChuteAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.bitchute.com/api/beta")

    async def video(self, video_id: str) -> Video:
        video = await self.request_json(self.ENTRYPOINT / "video", "POST", json={"video_id": video_id})
        return Video.parse(video)

    async def video_media(self, video_id: str) -> AbsoluteHttpURL:
        media = await self.request_json(self.ENTRYPOINT / "video/media", "POST", json={"video_id": video_id})
        return self.parse_url(media["media_url"])

    async def channel(self, channel_id: str) -> dict[str, str]:
        return await self.request_json(self.ENTRYPOINT / "channel", json={"channel_id": channel_id})

    async def channel_videos(
        self, channel_id: str, limit: int = 20, order_by: Literal["popular", "latest", "oldest"] = "latest"
    ) -> AsyncGenerator[Video]:
        url = self.ENTRYPOINT / "channel/videos"
        for offset in itertools.count(0, limit):
            resp = await self.request_json(
                url,
                "POST",
                json={
                    "channel_id": channel_id,
                    "offset": offset,
                    "limit": limit,
                    "order_by": order_by,
                },
            )

            for vid in resp["videos"]:
                yield Video.parse(vid)

            if len(resp["videos"]) < limit:
                break
