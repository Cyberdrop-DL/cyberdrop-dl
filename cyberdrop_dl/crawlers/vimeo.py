from __future__ import annotations

import asyncio
import dataclasses
import json
from typing import TYPE_CHECKING, Any, ClassVar, Self

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import DownloadError
from cyberdrop_dl.mediaprops import Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import extr_text, parse_url
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.json import JSONWebToken

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.url_objects import ScrapeItem


class VimeoCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/<video_id>",
            "/channels/<channel>/<video_id>",
            "https://player.vimeo.com/video/<id>",
        ),
    }

    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vimeo.com")
    DOMAIN: ClassVar[str] = "vimeo"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        host = scrape_item.url.host
        match scrape_item.url.parts[1:]:
            case ["video", video_id] if host == "player.vimeo.com":
                await self.video(scrape_item, video_id)
            case [video_id] | ["channels", _, video_id] if host == self.PRIMARY_URL.host:
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    def __post_init__(self) -> None:
        self.api: VimeoAPI = VimeoAPI.from_crawler(self)

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        try:
            config = await self.api.config_from_url(scrape_item.url)
        except Exception:  # noqa: BLE001
            config = await self.api.config_from_id(video_id)

        best = max(config.streams, key=lambda s: s.score)
        m3u8 = info = debrid_url = None
        if best.is_hls:
            m3u8, info = await self.request_m3u8_playlist(best.url)
        else:
            debrid_url = best.url

        await self.handle_file(
            scrape_item.url,
            scrape_item,
            config.meta.title,
            ext := ".mp4",
            m3u8=m3u8,
            thumbnail=config.meta.thumbnail_url,
            custom_filename=self.create_custom_filename(
                config.meta.title,
                ext,
                file_id=video_id,
                resolution=(info and info.resolution) or best.res,
                fps=(info and info.stream_info.frame_rate) or best.fps,
                video_codec=info and info.codecs.video,
                audio_codec=info and info.codecs.audio,
            ),
            debrid_link=debrid_url,
        )


@dataclasses.dataclass(slots=True, frozen=True)
class VimeoConfig:
    streams: tuple[Stream, ...]
    meta: Video
    owner: Owner

    @classmethod
    def parse(cls, config: dict[str, Any]) -> Self:
        return cls(
            tuple(parse_streams(config)),
            deserialize(Video, config["video"]),
            deserialize(Owner, config["video"]["owner"]),
        )


class VimeoAPI(API):
    VIEWER: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vimeo.com/_next/viewer")
    OEMBED: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vimeo.com/api/oembed.json")
    PLAYER: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://player.vimeo.com")

    def __post_init__(self) -> None:
        self._jwt_lock: asyncio.Lock = asyncio.Lock()
        self._jwt: JSONWebToken | None = None
        self.api_url: AbsoluteHttpURL

    async def _player_config(self, player_url: AbsoluteHttpURL) -> VimeoConfig:
        html = await self.request_text(player_url, headers={"Sec-GPC": "1"})
        config = json.loads(extr_text(html, "window.playerConfig =", "</script"))
        return VimeoConfig.parse(config)

    async def _config(self, config_url: AbsoluteHttpURL):
        resp = await self.request_json(config_url)
        return VimeoConfig.parse(resp)

    async def jwt(self) -> str:
        async with self._jwt_lock:
            if self._jwt is None or self._jwt.is_expired(300):
                resp = await self.request_json(self.VIEWER)
                self._jwt = JSONWebToken.decode(resp["jwt"])
                self.api_url = self.parse_url(resp["apiUrl"])

            return self._jwt.encoded

    async def _resolve_config_url(self, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        jwt = await self.jwt()
        uri = await self.request_json(self.OEMBED.with_query(url=str(url)))
        config_url = self.parse_url(uri, self.api_url).with_query(fields="config_url")
        resp = await self.request_json(config_url, headers={"Authorization": f"jwt {jwt}"})
        return self.parse_url(resp["config_url"])

    async def config_from_url(self, url: AbsoluteHttpURL) -> VimeoConfig:
        if "player" in url.host:
            return await self._player_config(url)

        config_url = await self._resolve_config_url(url)
        return await self._config(config_url)

    async def config_from_id(self, video_id: str) -> VimeoConfig:
        player_url = self.PLAYER / "video" / video_id
        config_url = player_url / "config"
        try:
            return await self._config(config_url)
        except DownloadError as e:
            if e.status not in (400, 403):
                raise
            return await self._player_config(player_url)


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class Owner:
    id: int
    name: str
    url: str
    account_type: str


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class Video:
    id: int
    title: str
    url: str
    duration: int
    privacy: str
    thumbnail_url: str


@dataclasses.dataclass(slots=True, frozen=True)
class Stream:
    name: str
    url: AbsoluteHttpURL
    res: Resolution
    is_hls: bool = False
    fps: int | None = None

    @property
    def score(self) -> tuple[bool, Resolution, int]:
        return (not self.is_hls, self.res, self.fps or 0)


def parse_streams(config: dict[str, Any]) -> Generator[Stream]:
    for kind, files in config["request"]["files"].items():
        match kind:
            case "hls":
                for name, opts in files["cdns"].items():
                    yield Stream(name=name, url=parse_url(opts["url"]), res=Resolution.unknown(), is_hls=True)

            case "progressive":
                for file in files:
                    yield Stream(
                        name=file["cdn"] + "-" + file["id"],
                        url=parse_url(file["url"]),
                        fps=int(file["fps"]),
                        res=Resolution(file["width"], file["height"]),
                    )
            case "dash":
                continue
            case _:
                VimeoCrawler.get_logger().warning("Unsupported stream(%s):\n%s", kind, files)
