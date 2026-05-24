from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


@dataclasses.dataclass(slots=True)
class Video:
    title: str
    id: str
    created_at: int
    src: AbsoluteHttpURL


class RutubeCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/video/<id>",
            "/play/embed/<id>",
        ),
    }

    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://rutube.ru")
    DOMAIN: ClassVar[str] = "rutube"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video", video_id]:
                return await self.video(scrape_item, video_id)
            case ["play", "embed", video_id]:
                return await self.embed(scrape_item, video_id)
            case _:
                raise ValueError

    def __post_init__(self) -> None:
        self.api: RutubeAPI = RutubeAPI(self)

    @error_handling_wrapper
    async def embed(self, scrape_item: ScrapeItem, embed_id: str) -> None:
        video = await self._request_video(embed_id)
        with scrape_item.track_changes():
            scrape_item.url = self.PRIMARY_URL / "video" / video.id

        if await self.check_complete_from_referer(scrape_item.url):
            return

        await self._video(scrape_item, video)

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        video = await self._request_video(video_id)
        await self._video(scrape_item, video)

    @error_handling_wrapper
    async def _video(self, scrape_item: ScrapeItem, video: Video) -> None:
        scrape_item.uploaded_at = video.created_at
        m3u8, info = await self.request_m3u8_playlist(video.src)
        filename = self.create_custom_filename(
            video.title,
            ext := ".mp4",
            file_id=video.id,
            resolution=info.resolution,
            video_codec=info.codecs.video,
            audio_codec=info.codecs.audio,
        )
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            video.title,
            ext,
            m3u8=m3u8,
            custom_filename=filename,
        )

    async def _request_video(self, video_id: str) -> Video:
        options = await self.api.play_options(video_id)
        video_id: str = options["effective_video"]
        created_at: str = (await self.api.metadata(video_id))["created_ts"]
        return Video(
            options["title"],
            video_id,
            created_at=self.parse_iso_date(created_at),
            src=self.parse_url(options["video_balancer"]["m3u8"]),
        )


class RutubeAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://rutube.ru/api")

    async def play_options(self, video_id: str) -> dict[str, Any]:
        url = (self.ENTRYPOINT / "play/options" / video_id).with_query(format="json", mq="all", av1=1)
        return await self.request_json(url)

    async def metadata(self, video_id: str) -> dict[str, Any]:
        url = (self.ENTRYPOINT / "video" / video_id).with_query(format="json")
        return await self.request_json(url)
