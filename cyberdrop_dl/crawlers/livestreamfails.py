from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import API, Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import deserialize, error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.url_objects import ScrapeItem


class _CDN:
    IMAGE = AbsoluteHttpURL("https://media-prod.livestreamfails.com/image")
    VIDEO = AbsoluteHttpURL("https://livestreamfails-video-prod.b-cdn.net/video")


class LivestreamFailsCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Clip": "/clip/<video_id>",
        "Streamer": "/streamer/<streamer_id>",
    }
    DOMAIN: ClassVar[str] = "livestreamfails.com"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://livestreamfails.com")
    _RATE_LIMIT: ClassVar[RateLimit] = 8, 1

    def __post_init__(self) -> None:
        self.api: LivestreamFailsAPI = LivestreamFailsAPI(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["clip", clip_id]:
                return await self.clip(scrape_item, clip_id)
            case ["streamer", streamer_id]:
                return await self.streamer(scrape_item, streamer_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def streamer(self, scrape_item: ScrapeItem, streamer_id: str) -> None:
        scrape_item.setup_as_profile("")
        async for videos in self.api.streamer_clips(streamer_id):
            for video in videos:
                url = self.PRIMARY_URL / f"clip/{video.id}"
                new_item = scrape_item.create_child(url)
                self.create_task(self._clip(new_item, video))
                scrape_item.add_children()

    @error_handling_wrapper
    async def clip(self, scrape_item: ScrapeItem, clip_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        video = await self.api.clip(clip_id)
        await self._clip(scrape_item, video)

    @error_handling_wrapper
    async def _clip(self, scrape_item: ScrapeItem, clip: Clip) -> None:
        scrape_item.setup_as_album(self.create_title(clip.streamer.label, str(clip.streamer.id)))
        scrape_item.uploaded_at = self.parse_iso_date(clip.createdAt)
        _, ext = self.get_filename_and_ext(clip.src.name)
        filename = self.create_custom_filename(clip.label, ext, file_id=str(clip.id))
        await self.handle_file(clip.src, scrape_item, clip.label, ext, custom_filename=filename, metadata=clip)


@dataclasses.dataclass(slots=True)
class Clip:
    id: int
    label: str
    createdAt: str  # noqa: N815
    streamer: Streamer
    src: AbsoluteHttpURL
    thumbnail: AbsoluteHttpURL


@dataclasses.dataclass(slots=True)
class Streamer:
    id: int
    label: str


class LivestreamFailsAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.livestreamfails.com")

    async def clip(self, clip_id: str) -> Clip:
        api_url = self.ENTRYPOINT / "clip" / clip_id
        video: dict[str, Any] = await self.request_json(api_url)
        return _parse_video(video)

    def streamer_clips(self, streamer_id: str) -> AsyncGenerator[map[Clip]]:
        api_url = self.ENTRYPOINT / "streamer" / streamer_id / "clips"
        return self._pager(api_url)

    async def _pager(self, url: AbsoluteHttpURL) -> AsyncGenerator[map[Clip]]:
        url = url.update_query(querySort="new")
        while True:
            resp = await self.request_json(url)
            if not resp:
                break
            last_id: str = resp[-1]["id"]
            yield map(_parse_video, resp)
            if len(resp) < 20:
                break
            url = url.update_query(queryAfter=last_id)


def _parse_video(resp: dict[str, Any]) -> Clip:
    return deserialize(
        Clip,
        resp,
        src=_CDN.VIDEO / resp["videoId"],
        thumbnail=_CDN.IMAGE / resp["imageId"],
        streamer=deserialize(Streamer, resp["streamer"]),
    )
