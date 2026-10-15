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
        "Audio": (
            "/audio/<audio_id>",
            "/brand/<brand>#playing_audio=<audio_id>",
        ),
    }
    DOMAIN: ClassVar[str] = "smotrim.ru"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://smotrim.ru")

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        def frag_get(name: str) -> str | None:
            if url.fragment.startswith(pf := f"{name}="):
                return url.fragment.removeprefix(pf) or None

        url = super().transform_url(url)
        match url.parts[1:]:
            case ["brand", _] if video_id := frag_get("playing_video"):
                return url.origin() / "video" / video_id
            case ["brand", _] if audio_id := frag_get("playing_audio"):
                return url.origin() / "audio" / audio_id
            case ["iframe", "video", "id", video_id]:
                return cls.PRIMARY_URL / "video" / video_id
            case _:
                return url

    def __post_init__(self) -> None:
        self.api: SmotrimAPI = SmotrimAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video" | "audio" as kind, media_id]:
                await self.media(scrape_item, kind, media_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def media(self, scrape_item: ScrapeItem, kind: str, media_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        media = await self.api.media(kind, media_id)
        await self._media(scrape_item, media)

    @error_handling_wrapper
    async def _media(self, scrape_item: ScrapeItem, media: Media) -> None:
        scrape_item.setup_as_album(self.create_title(media.series.name, str(media.series.id)))
        scrape_item.uploaded_at = self.parse_iso_date(media.episode.airDate)

        if media.src.suffix == ".m3u8":
            m3u8, _ = await self.request_m3u8(media.src)
            ext, debrid_link = ".mp4", None
        else:
            m3u8, debrid_link = None, media.src
            _, ext = self.get_filename_and_ext(media.src.name)

        if media.series.type == "film":
            name = media.series.name
        else:
            name = compose_ep_name(media.episode.season, media.episode.number, media.episode.title)

        await self.handle_file(
            scrape_item.url,
            scrape_item,
            name,
            ext,
            custom_filename=self.create_custom_filename(name, ext, file_id=str(media.publicId)),
            metadata=Media,
            m3u8=m3u8,
            debrid_link=debrid_link,
            thumbnail=media.episode.thumb,
        )


@dataclasses.dataclass(slots=True, frozen=True)
class Media:
    id: int
    publicId: int  # noqa: N815
    episode: Episode
    series: Series
    src: AbsoluteHttpURL

    @classmethod
    def parse(cls, data: dict[str, Any]) -> Self:
        streams = data["streams"]
        return deserialize(
            cls,
            data,
            series=deserialize(Series, data["brand"]),
            episode=Episode.parse(data["episode"]),
            src=SmotrimCrawler.parse_url(streams.get("m3u8") or streams["mp3"]),
        )


@dataclasses.dataclass(slots=True, frozen=True)
class Series:
    id: int
    title: str
    type: str
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
        season = ep.get("season")
        return deserialize(
            cls,
            ep,
            season=season.get("number") if season else None,
            thumb=ep.get("splash", {}).get("large"),
        )


class SmotrimAPI(API):
    PLAYER: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://player-api.smotrim.ru/api/v1")

    async def media(self, kind: str, media_id: str) -> Media:
        api_url = self.PLAYER / kind / media_id
        resp = await self.request_json(api_url)
        return Media.parse(resp["data"])
