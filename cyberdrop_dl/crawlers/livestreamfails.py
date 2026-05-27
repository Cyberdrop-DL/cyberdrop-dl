from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import deserialize, error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class _CDN:
    IMAGE = AbsoluteHttpURL("https://media-prod.livestreamfails.com/image")
    VIDEO = AbsoluteHttpURL("https://livestreamfails-video-prod.b-cdn.net/video")


_API_ENTRYPOINT = AbsoluteHttpURL("https://api.livestreamfails.com")


@dataclasses.dataclass(slots=True)
class Video:
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


class LivestreamFailsCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Video": ("/clip/<video_id>",)}
    DOMAIN: ClassVar[str] = "livestreamfails.com"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://livestreamfails.com")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["clip", video_id]:
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        video = await self._request_video(video_id)
        scrape_item.setup_as_album(self.create_title(video.streamer.label, str(video.streamer.id)))
        scrape_item.uploaded_at = self.parse_iso_date(video.createdAt)
        _, ext = self.get_filename_and_ext(video.src.name)
        filename = self.create_custom_filename(video.label, ext, file_id=video_id)
        await self.handle_file(video.src, scrape_item, video.label, ext, custom_filename=filename, metadata=video)

    async def _request_video(self, video_id: str) -> Video:
        api_url = _API_ENTRYPOINT / "clip" / video_id
        resp: dict[str, Any] = await self.request_json(api_url)
        return deserialize(
            Video,
            resp,
            src=_CDN.VIDEO / resp["videoId"],
            thumbnail=_CDN.IMAGE / resp["imageId"],
            streamer=deserialize(Streamer, resp["streamer"]),
        )
