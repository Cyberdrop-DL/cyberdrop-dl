from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths, compose_ep_name
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class SmotrimCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/video/<video_id>",
            "/brand/<brand>#playing_video=<video_id>",
        ),
    }
    DOMAIN: ClassVar[str] = "smotrim.ru"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://smotrim.ru")

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["brand", _] if url.fragment.startswith(pf := "playing_video=") and (
                video_id := url.fragment.removeprefix(pf)
            ):
                return url.origin() / "video" / video_id
            case _:
                return url

    def __post_init__(self) -> None:
        self.api: SmotrimAPI = SmotrimAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video", video_id]:
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        video = await self.api.video(video_id)
        scrape_item.setup_as_album(self.create_title(video.series.name, str(video.series.id)))
        scrape_item.uploaded_at = self.parse_iso_date(video.episode.airDate)
        m3u8, _ = await self.request_m3u8(video.m3u8)
        name = compose_ep_name(video.episode.season, video.episode.number, video.episode.title)
        filename = self.create_custom_filename(name, ext := ".mp4", file_id=video_id)
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            video.episode.title or name,
            ext,
            m3u8=m3u8,
            custom_filename=filename,
            metadata=Video,
            thumbnail=video.episode.thumb,
        )


@dataclasses.dataclass(slots=True, frozen=True)
class Video:
    id: int
    publicId: int  # noqa: N815
    episode: Episode
    series: Series
    m3u8: AbsoluteHttpURL


@dataclasses.dataclass(slots=True, frozen=True)
class Series:
    id: int
    title: str
    yearReleasedFrom: int | None = None  # noqa: N815

    @property
    def name(self) -> str:
        if self.yearReleasedFrom:
            return f"{self.title} ({self.yearReleasedFrom})"
        return self.title


@dataclasses.dataclass(slots=True, frozen=True)
class Episode:
    id: int
    title: str | None
    airDate: str  # noqa: N815
    number: int
    season: int | None
    thumb: str | None

    @classmethod
    def parse(cls, ep: dict[str, Any]) -> Self:
        return deserialize(
            cls,
            ep,
            season=ep["season"].get("number"),
            thumb=ep.get("splash", {}).get("large"),
        )


class SmotrimAPI(API):
    PLAYER: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://player-api.smotrim.ru/api/v1")

    async def player_data(self, kind: str, media_id: str) -> dict[str, Any]:
        api_url = self.PLAYER / kind / media_id
        return (await self.request_json(api_url))["data"]

    async def video(self, video_id: str) -> Video:
        data = await self.player_data("video", video_id)
        return deserialize(
            Video,
            data,
            series=deserialize(Series, data["brand"]),
            episode=Episode.parse(data["episode"]),
            m3u8=self.parse_url(data["streams"]["m3u8"]),
        )
