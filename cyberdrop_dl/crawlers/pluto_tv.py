from __future__ import annotations

import dataclasses
import itertools
import uuid
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, ClassVar, override

import yarl
from typing_extensions import AsyncGenerator

from cyberdrop_dl.cache import cached_method
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths, compose_ep_name
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import css, next_js
from cyberdrop_dl.utils.dataclass import Deserializer
from cyberdrop_dl.utils.errors import error_handling_wrapper

session_token: ContextVar[str] = ContextVar("session_token")

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.utils.m3u8 import Rendition


class PlutoCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Episode": (".../shows/<show_id>/episode/<episode_id>",),
        "Show": (".../shows/<show_slug>",),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pluto.tv")
    DOMAIN: ClassVar[str] = "pluto.tv"

    @staticmethod
    @override
    def __db_path__(url: AbsoluteHttpURL, /) -> str:
        _region, sep, rest = url.path.partition("/shows/")
        assert sep
        return sep + rest

    def __post_init__(self) -> None:
        self.api: PlutoAPI = PlutoAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [*_, "shows", show_id, "episode", episode_id]:
                await self.episode(scrape_item, show_id, episode_id)
            case [*_, "shows", show_id]:
                await self.show(scrape_item, show_id)
            case [*_, "shows", show_id, "season", _season]:
                await self.show(scrape_item, show_id)

            case _:
                raise ValueError

    @error_handling_wrapper
    async def show(self, scrape_item: ScrapeItem, show_slug: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        data = next_js.data(soup)
        ep = data["props"]["pageProps"]["dehydratedState"]["queries"]
        episode = _deserialize(Episode, ep, id=show_slug)
        scrape_item.setup_as_album(self.create_title(ep["seriesTitle"], show_slug), album_id=show_slug)
        await self._episode(scrape_item, episode)

    @error_handling_wrapper
    async def episode(self, scrape_item: ScrapeItem, series_id: str, episode_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        data = next_js.data(soup)
        ep = data["props"]["pageProps"]["episodeMetadata"]
        episode = _deserialize(Episode, ep, id=episode_id)
        scrape_item.setup_as_album(self.create_title(ep["seriesTitle"], series_id), album_id=series_id)
        await self._episode(scrape_item, episode)

    @error_handling_wrapper
    async def _episode(self, scrape_item: ScrapeItem, ep: Episode) -> None:
        m3u8_url = await self.api.stream(ep.id)
        m3u8, info = await self.request_m3u8_playlist(
            m3u8_url, headers={"User-Agent": self.api.FIREFOX}, keep_query=True
        )
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


class PlutoAPI(API):
    FIREFOX: ClassVar[str] = "Mozilla/5.0 (X11; Linux x86_64; rv:151.0) Gecko/20100101 Firefox/151.0"
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
            headers={"User-Agent": self.FIREFOX},
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

    async def series_seasons(self, series_id: str) -> AsyncGenerator[Generator[Episode]]:
        session = await self.start()
        rul = (self.SERIES / series_id / "seasons").with_query(offset=0)
        for page in itertools.count(0):
            resp = await self.request_json(rul.update_query(page=page), headers={"Autorization": session.jwt})
            yield (_deserialize(Episode, ep) for ep in resp["seasons"]["episodes"])


@dataclasses.dataclass(slots=True, frozen=True)
class Session:
    id: str
    jwt: str


_deserialize = Deserializer(
    {"season": "seasonNum", "number": "episodeNum"},
    {"season": int, "number": int},
)


@dataclasses.dataclass(slots=True, frozen=True)
class Episode:
    id: str
    description: str
    season: int
    number: int
    title: str


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
