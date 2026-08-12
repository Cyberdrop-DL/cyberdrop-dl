from __future__ import annotations

import dataclasses
import uuid
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, ClassVar, TypedDict

import yarl

from cyberdrop_dl.cache import cached_method
from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths, auto_task_id, compose_ep_name
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import css, extr_text, next_js
from cyberdrop_dl.utils.dataclass import Deserializer
from cyberdrop_dl.utils.errors import error_handling_wrapper

session_token: ContextVar[str] = ContextVar("session_token")

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.utils.m3u8 import Rendition

FIREFOX = "Mozilla/5.0 (X11; Linux x86_64; rv:151.0) Gecko/20100101 Firefox/151.0"


@HTTPConfig.default_headers(user_agent=FIREFOX)
class PlutoCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Episode": "<region>/shows/<show_id>/episode/<episode_id>",
        "Show": (
            "<region>/shows/<show_slug>",
            "<region>/shows/<show_slug>/season/<season>",
        ),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pluto.tv")
    DOMAIN: ClassVar[str] = "pluto.tv"

    def __post_init__(self) -> None:
        self.api: PlutoAPI = PlutoAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [*_, "shows", show_id, "episode", episode_id]:
                await self.episode(scrape_item, show_id, episode_id)
            case [*_, "shows", show_id]:
                await self.show(scrape_item, show_id)
            case [*_, "shows", show_id, "season", season]:
                await self.show(scrape_item, show_id, int(season))
            case _:
                raise ValueError

    @error_handling_wrapper
    async def show(self, scrape_item: ScrapeItem, show_slug: str, season: int | None = None) -> None:
        scrape_item.setup_as_album("")

        async with self.request(scrape_item.url) as resp:
            text = await resp.text()
            scrape_item.url = resp.url

        series_id = extr_text(text, "/ptvm/series/", "/")
        series = await self.api.series(series_id)
        downloaded = await self.get_album_results(series.id)
        scrape_item.setup_as_album(self.create_title(series.title, series.id), album_id=series.id)

        base_url = self.PRIMARY_URL.with_path(scrape_item.url.path.partition(show_slug)[0]) / show_slug
        for ep in series.episodes():
            if season is not None and ep.season != season:
                continue

            url = base_url / "episode" / ep.id
            if self.check_album_results(url, downloaded):
                continue

            new_item = scrape_item.create_child(url)
            self.create_task(self._episode_task(new_item, ep))
            scrape_item.add_children()

    @error_handling_wrapper
    async def episode(self, scrape_item: ScrapeItem, series_id: str, episode_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        async with self.request(scrape_item.url) as resp:
            soup = await resp.soup()
            scrape_item.url = resp.url

        props = next_js.data(soup)["props"]["pageProps"]
        ep = props["episodeMetadata"]
        episode = _deserialize(Episode, ep, id=episode_id)
        scrape_item.setup_as_album(self.create_title(ep["seriesTitle"], series_id), album_id=series_id)
        await self._episode(scrape_item, episode)

    async def _episode(self, scrape_item: ScrapeItem, ep: Episode) -> None:
        scrape_item.uploaded_at = self.parse_iso_date(ep.airDateISO)
        m3u8_url = await self.api.stream(ep.id)
        m3u8, info = await self.request_m3u8_playlist(m3u8_url, keep_query=True)
        _remove_ads_segments(m3u8)
        filename = self.create_custom_filename(
            compose_ep_name(ep.season, ep.number, ep.title),
            ext := ".mp4",
            file_id=ep.id,
            resolution=info.resolution,
            video_codec=info.codecs.video or "avc1",
            audio_codec=info.codecs.audio,
            fps=info.stream_info.frame_rate,
        )
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            ep.title,
            ext,
            m3u8=m3u8,
            custom_filename=filename,
            metadata=ep,
        )

    _episode_task = auto_task_id(error_handling_wrapper(_episode))


@HTTPConfig.default_headers(user_agent=FIREFOX)
class PlutoAPI(API):
    GRAPHQL_ENDPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pluto.tv/api/tn/app-shell/graphql/")
    SERIES: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://service-vod.clusters.pluto.tv/v4/vod/series/")
    M3U8: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL(
        "https://cfd-v4-service-channel-stitcher-use1-1.prd.pluto.tv/v2/stitch/hls/episode"
    )

    def __post_init__(self) -> None:
        self._device_version: str = "151.0.0"  # from firefox's UA
        self._client_id: str = str(uuid.uuid4())

    def __repr__(self) -> str:
        return f"<{type(self).__name__}(app_version={self.app_version.get()}, client_id={self._client_id}, device_version={self._device_version})>"

    @cached_method()
    async def app_version(self) -> str:
        soup = await self.request_soup(self.PRIMARY_URL)
        return css.select(soup, "meta[name=appVersion], meta[name=app_version]", "content")

    @cached_method(ttl=1800)
    async def start(self) -> Session:
        resp = await self.request_gql(
            "PtvStart",
            {
                "params": {
                    "deviceModel": "web",
                    "drmCapabilities": "widevine:L3",
                    "isClientDNT": True,
                    "deviceId": self._client_id,
                    "ptvAppName": "web",
                    "cmAudienceID": "",
                    "updateType": "v1v2",
                }
            },
        )

        return _deserialize(Session, resp["ptvStart"]["session"])

    async def request_gql(self, operation: str, variables: dict[str, Any]) -> dict[str, Any]:
        resp = await self.request_json(
            self.GRAPHQL_ENDPOINT,
            method="POST",
            json={
                "query": globals()[operation],
                "variables": variables,
                "operationName": operation,
            },
        )
        return resp["data"]

    async def stream(self, episode_id: str) -> AbsoluteHttpURL:
        session = await self.start()
        url = self.M3U8 / episode_id / "master.m3u8"
        return url.with_query(
            {
                "advertisingId": "",
                "appName": "web",
                "appVersion": await self.app_version(),
                "app_name": "web",
                "clientID": self._client_id,
                "deviceId": self._client_id,
                "deviceMake": "firefox",
                "deviceModel": "web",
                "deviceType": "web",
                "deviceVersion": "151.0",
                "serverSideAds": "false",
                "sessionID": session.id,
                "sid": session.id,
                "userId": "",
                "jwt": session.jwt,
                "includeExtendedEvents": "true",
            }
        )

    async def series(self, series_id: str) -> Series:
        session = await self.start()
        url = (self.SERIES / series_id / "seasons").with_query(offset=0)
        resp = await self.request_json(url, headers={"Authorization": f"Bearer {session.jwt}"})
        return _deserialize(Series, resp)


@dataclasses.dataclass(slots=True, frozen=True)
class Session:
    id: str
    jwt: str


_deserialize = Deserializer(
    {"season": "seasonNum", "number": "episodeNum", "title": "name", "id": "_id"},
    {"season": int, "number": int},
)


@dataclasses.dataclass(slots=True, frozen=True)
class Episode:
    id: str
    description: str
    season: int
    number: int
    title: str
    airDateISO: str  # noqa: N815


class Season(TypedDict):
    number: int
    episodes: list[dict[str, Any]]


@dataclasses.dataclass(slots=True)
class Series:
    id: str
    title: str
    slug: str
    seasons: list[Season] = dataclasses.field(default_factory=list)

    def episodes(self) -> Generator[Episode]:
        for season in self.seasons:
            for ep in season["episodes"]:
                yield _deserialize(Episode, ep)


def _remove_ads_segments(rendition: Rendition) -> None:
    for m3u8 in rendition:
        if not m3u8:
            continue

        m3u8.data["segments"] = [s for s in m3u8.data["segments"] if not _is_ad(s["uri"])]
        m3u8._initialize_attributes()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]


def _is_ad(uri: str) -> bool:
    path = yarl.URL(uri).path.casefold()
    return any(ad_name in path for ad_name in ("_ad%2f", "_ad/", "_ad_bumper", "plutotv_filler"))


PtvStart = """
query PtvStart($params: StartParameters!) {
  ptvStart(params: $params) {
    deviceId
    session {
      id
      jwt
    }
    refreshInSec
  }
}
"""
