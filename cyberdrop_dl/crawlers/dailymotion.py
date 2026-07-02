from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, override

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import PasswordProtectedError
from cyberdrop_dl.mediaprops import Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import parse_url
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.url_objects import ScrapeItem


class DailyMotionCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "video/<video_uid>",
    }

    DOMAIN: ClassVar[str] = "dailymotion"
    FOLDER_DOMAIN: ClassVar[str] = "CloudflareStream"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.dailymotion.com")

    def __post_init__(self) -> None:
        self.api: DailyMotionAPI = DailyMotionAPI.from_crawler(self)

    @override
    async def __async_post_init__(self) -> None:
        self.update_cookies(
            {
                "family_filter": "off",
                "ff": "off",
            },
            AbsoluteHttpURL("https://dailymotion.com"),
        )

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video", video_id]:
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        video = await self.api.video(video_id)
        scrape_item.uploaded_at = video.created_time
        best = video.streams[0]
        m3u8, info = await self.request_m3u8_playlist(best.url, headers={"priority": "u=1, i"})
        filename = self.create_custom_filename(
            video.title,
            ext := ".mp4",
            file_id=video_id,
            resolution=info.resolution,
            fps=best.fps,
        )
        await self.handle_file(scrape_item.url, scrape_item, video.title, ext, m3u8=m3u8, custom_filename=filename)


@dataclasses.dataclass(slots=True, order=True)
class Video:
    title: str
    created_time: int
    streams: tuple[Stream, ...]


@dataclasses.dataclass(slots=True, order=True)
class Stream:
    resolution: Resolution
    type: str
    fps: float | None
    url: AbsoluteHttpURL


class DailyMotionAPI(API):
    async def metadata(self, video_id: str) -> dict[str, Any]:
        url = self.PRIMARY_URL / "player/metadata/video" / video_id
        return await self.request_json(url)

    async def video(self, video_id: str) -> Video:
        metadata = await self.metadata(video_id)
        # TODO: handle this
        if metadata.get("is_password_protected"):
            raise PasswordProtectedError

        return deserialize(Video, metadata, streams=tuple(_parse_streams(metadata["qualities"])))


def _parse_streams(qualities: dict[str, list[dict[str, str]]]) -> Generator[Stream]:
    for quality, streams in qualities.items():
        if quality == "auto":
            res, fps = Resolution.unknown(), None
        else:
            res, _, fps = quality.partition("@")
            res, fps = Resolution.parse(res), float(fps) if fps else None

        for stream in streams:
            url = parse_url(stream["url"], trim=False)
            yield Stream(res, stream["type"], fps, url)
