from __future__ import annotations

import dataclasses
import itertools
import logging
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, ClassVar, override

from cyberdrop_dl import signature
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import PasswordProtectedError, ScrapeError
from cyberdrop_dl.mediaprops import Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import parse_url
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from cyberdrop_dl.clients.response import AbstractResponse
    from cyberdrop_dl.url_objects import ScrapeItem

logger = logging.getLogger(__name__)


class DailyMotionCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/video/<video_uid>",
        "Playlist": "/playlist/<slug>",
    }

    DOMAIN: ClassVar[str] = "dailymotion"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.dailymotion.com")

    @classmethod
    @override
    def __json_resp_check__(cls, json_resp: dict[str, Any], resp: AbstractResponse[Any] | None, /) -> None:
        # https://developers.dailymotion.com/reference/api-errors
        if error := json_resp.get("error"):
            message = error.get("raw_message") or error.get("message")
            code = _VIDEO_ERRORS.get(error.get("code", "")) or error.get("status_code") or resp.status if resp else 422
            raise ScrapeError(code, message)

    def __post_init__(self) -> None:
        self.api: DailyMotionAPI = DailyMotionAPI.from_crawler(self)
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
            case ["playlist", slug]:
                return await self.playlist(scrape_item, slug)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        video = await self.api.video(video_id)
        scrape_item.uploaded_at = video.created_time
        best_stream = _select_stream(video)
        m3u8, info = await self.request_m3u8_playlist(
            best_stream.url, headers={"Referer": str(scrape_item.url), "priority": "u=1, i"}
        )
        filename = self.create_custom_filename(
            video.title,
            ext := ".mp4",
            file_id=video_id,
            resolution=info.resolution,
            fps=best_stream.fps,
        )
        await self.handle_file(scrape_item.url, scrape_item, video.title, ext, m3u8=m3u8, custom_filename=filename)

    @error_handling_wrapper
    async def playlist(self, scrape_item: ScrapeItem, slug: str) -> None:
        playlist = await self.api.playlist(slug)
        title = self.create_title(playlist.name, playlist.id)
        scrape_item.setup_as_album(title, album_id=playlist.id)

        async for videos in self.api.playlist_videos(playlist.id):
            for video_url in videos:
                new_item = scrape_item.create_child(video_url)
                self.create_task(self.run(new_item))
                scrape_item.add_children()


@dataclasses.dataclass(slots=True, order=True)
class Video:
    id: str
    title: str
    created_time: int
    streams: tuple[Stream, ...]


@dataclasses.dataclass(slots=True, order=True)
class Stream:
    resolution: Resolution
    fps: float | None
    url: AbsoluteHttpURL


@dataclasses.dataclass(slots=True, order=True)
class Playlist:
    id: str
    name: str
    owner: str


class DailyMotionAPI(API):
    # https://developers.dailymotion.com/reference/perform-an-api-call
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.dailymotion.com")

    @override
    @signature.copy(API.request_json)
    async def request_json(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        data = await super().request_json(*args, **kwargs)
        # Check for errors even on 200 responses
        DailyMotionCrawler.__json_resp_check__(data, None)
        return data

    async def metadata(self, video_id: str) -> dict[str, Any]:
        api_url = self.PRIMARY_URL / "player/metadata/video" / video_id
        video_url = self.PRIMARY_URL / "video" / video_id
        return await self.request_json(api_url, headers={"Referer": str(video_url)})

    async def video(self, video_id: str) -> Video:
        metadata = await self.metadata(video_id)
        if metadata.get("isOnAir"):
            raise ScrapeError(422, "Live streams are not supported")

        # TODO: handle password protected videos
        if metadata.get("is_password_protected"):
            raise PasswordProtectedError

        return deserialize(Video, metadata, streams=tuple(_parse_streams(metadata["qualities"])))

    async def playlist(self, slug: str) -> Playlist:
        url = self.ENTRYPOINT / "playlist" / slug
        data = await self.request_json(url)
        return deserialize(Playlist, data)

    async def playlist_videos(self, playlist_id: str) -> AsyncGenerator[Generator[AbsoluteHttpURL]]:
        url = (self.ENTRYPOINT / "playlist" / playlist_id / "videos").with_query(limit=100, fields="id")
        for page in itertools.count(2):
            data = await self.request_json(url)
            yield (self.PRIMARY_URL / "video" / video["id"] for video in data["list"])
            if not data["has_more"]:
                break
            url = url.update_query(page=page)


def _parse_streams(qualities: dict[str, list[dict[str, str]]]) -> Generator[Stream]:
    for quality, streams in qualities.items():
        if quality == "auto":
            res, fps = Resolution.unknown(), None
        else:
            res, _, fps = quality.partition("@")
            res, fps = Resolution.parse(res), float(fps) if fps else None

        for stream in streams:
            url = parse_url(stream["url"], trim=False)
            yield Stream(res, fps, url)


def _select_stream(video: Video) -> Stream:
    match len(video.streams):
        case 0:
            raise ScrapeError(422, f"Unable to parse any stream for video {video.id}")
        case 1:
            assert video.streams[0].url.suffix == ".m3u8"
            return video.streams[0]
        case _:
            logger.debug("Found multiple streams for video %s. Falling back to HLS auto", video.id)
            return next(s for s in video.streams if s.url.suffix == ".m3u8" and s.resolution == Resolution.unknown())


_VIDEO_ERRORS = {
    "DM002": HTTPStatus.GONE,
    "DM004": HTTPStatus.FORBIDDEN,
    "DM005": HTTPStatus.UNAVAILABLE_FOR_LEGAL_REASONS,
    "DM007": HTTPStatus.FORBIDDEN,
    "DM010": HTTPStatus.UNAUTHORIZED,
}
