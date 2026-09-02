from __future__ import annotations

import itertools
from typing import Any, ClassVar, Self

from pydantic import dataclasses

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.mediaprops import ISO639Subtitle, Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper


class PeerTubeCrawler(Crawler, is_generic=True):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/videos/watch/0b04f13d-1e18-4f1d-814e-4979aa7c9c44",
            "/w/<video_id>",
        ),
    }

    def __init_subclass__(cls, **kwargs: Any) -> None:
        cls.DOMAIN = cls.PRIMARY_URL.host
        return super().__init_subclass__(**kwargs)

    def __post_init__(self) -> None:
        self.api: PeerTubeAPI = PeerTubeAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["w", video_id]:
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        video = await self.api.video(video_id, scrape_item.password)
        scrape_item.uploaded_at = self.parse_iso_date(video.publishedAt)
        best_src = max(video.files)
        _, ext = self.get_filename_and_ext(best_src.fileUrl.name)
        filename = self.create_custom_filename(
            video.name, ext, file_id=video_id, resolution=best_src.resolution, fps=best_src.fps
        )
        subs = await self.api.captions(video_id, scrape_item.password)
        self.handle_subs(scrape_item, filename, subs)
        await self.handle_file(
            best_src.fileUrl,
            scrape_item,
            video.name,
            ext,
            custom_filename=filename,
            thumbnail=video.thumb,
            headers=self.api.headers(scrape_item.password),
        )


class PeerTubeAPI(API):
    @classmethod
    def headers(cls, password: str | None) -> dict[str, Any]:
        return {"x-peertube-video-password": password} if password else {}

    async def video(self, video_id: str, password: str | None) -> Video:
        url = self.PRIMARY_URL / "api/v1/videos" / video_id
        resp = await self.request_json(url, headers=self.headers(password))
        return Video.parse(resp)

    async def captions(self, video_id: str, password: str | None) -> list[ISO639Subtitle]:
        url = self.PRIMARY_URL / "api/v1/videos" / video_id / "captions"
        resp = await self.request_json(url, headers=self.headers(password))
        return [ISO639Subtitle(sub["fileUrl"], sub["language"]["id"], sub["language"]["label"]) for sub in resp["data"]]


@dataclasses.dataclass(slots=True, frozen=True)
class Video:
    uuid: str
    name: str
    url: AbsoluteHttpURL
    thumb: AbsoluteHttpURL
    publishedAt: str  # noqa: N815
    files: tuple[File, ...]

    @property
    def web_path(self) -> str:
        return f"/videos/watch/{self.uuid}"

    @classmethod
    def parse(cls, video: dict[str, Any]) -> Self:
        if video.get("isLive"):
            raise ScrapeError(422, "Livestreams are not supported")

        *_, thumb = max((t["width"], t["height"], t["fileUrl"]) for t in video["thumbnails"])

        files = itertools.chain.from_iterable(p["files"] for p in video["streamingPlaylists"])
        files = itertools.chain(video["files"], files)
        return deserialize(cls, video, thumb=thumb, files=map(File.parse, files))


@dataclasses.dataclass(slots=True, frozen=True, order=True)
class File:
    resolution: Resolution
    fps: int | None
    size: int
    fileUrl: AbsoluteHttpURL  # noqa: N815

    @classmethod
    def parse(cls, file: dict[str, Any]) -> Self:
        return deserialize(cls, file, resolution=Resolution(file["width"], file["height"]))


class FramaTubeCrawler(PeerTubeCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://framatube.org")
