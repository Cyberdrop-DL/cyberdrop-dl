from __future__ import annotations

import dataclasses
import itertools
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, ClassVar, override

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


class DailyMotionCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/video/<video_uid>",
        "Playlist": "/playlist/<slug>",
    }

    DOMAIN: ClassVar[str] = "dailymotion"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.dailymotion.com")

    @classmethod
    @override
    def __json_resp_check__(cls, json_resp: dict[str, Any], resp: AbstractResponse[Any], /) -> None:
        if error := json_resp.get("error"):
            # See https://developer.dailymotion.com/api#access-error
            message, code = _VIDEO_ERRORS.get(error.get("code", ""), (error["message"], resp.status))
            raise ScrapeError(code, message)

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
    title: str
    created_time: int
    streams: tuple[Stream, ...]


@dataclasses.dataclass(slots=True, order=True)
class Stream:
    resolution: Resolution
    type: str
    fps: float | None
    url: AbsoluteHttpURL


@dataclasses.dataclass(slots=True, order=True)
class Playlist:
    name: str
    id: str
    owner: str


class DailyMotionAPI(API):
    # https://developers.dailymotion.com/reference/perform-an-api-call
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.dailymotion.com")

    async def metadata(self, video_id: str) -> dict[str, Any]:
        url = self.PRIMARY_URL / "player/metadata/video" / video_id
        return await self.request_json(url)

    async def video(self, video_id: str) -> Video:
        metadata = await self.metadata(video_id)
        # TODO: handle this
        if metadata.get("is_password_protected"):
            raise PasswordProtectedError

        if metadata.get("isOnAir"):
            raise ScrapeError(422, "Live streams are not supported")

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
            yield Stream(res, stream["type"], fps, url)


_VIDEO_ERRORS = {
    "DM002": ("Content has been deleted", HTTPStatus.GONE),
    "DM004": ("Copyrighted content, access forbidden", HTTPStatus.FORBIDDEN),
    "DM005": (
        "Content rejected (this video may have been removed due to a breach of the terms of use, a copyright claim or an infringement upon third party rights)",
        HTTPStatus.UNAVAILABLE_FOR_LEGAL_REASONS,
    ),
    "DM007": ("Video geo-restricted by its owner", HTTPStatus.FORBIDDEN),
    "DM010": ("Private content", HTTPStatus.UNAUTHORIZED),
}
