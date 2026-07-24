from __future__ import annotations

import dataclasses
import uuid
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, ClassVar, TypedDict, override

import yarl

from cyberdrop_dl.cache import cached_method
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths, compose_ep_name
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.utils.m3u8 import Rendition


class PlutoCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Series": (
            "/on-demand/<series_id>",
            "/<region>/on-demand/<series_id>",
        ),
        "Season": ".../no-demand/<series_id>/season/<season>",
        "Episode": (
            ".../no-demand/<series_id>/episode/<episode_id>",
            ".../no-demand/<series_id>/season/<season>/episode/<episode_id>",
        ),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pluto.tv")
    DOMAIN: ClassVar[str] = "pluto.tv"

    @staticmethod
    @override
    def __db_path__(url: AbsoluteHttpURL, /) -> str:
        _region, sep, rest = url.path.partition("/on-demand/")
        return sep + rest

    def __post_init__(self) -> None:
        self.api: PlutoAPI = PlutoAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_, "on-demand", *vod] | ["on-demand", *vod]:
                match vod:
                    case ["series", series_id, *rest]:
                        match rest:
                            case ["season", _, "episode", episode_id] | ["episode", episode_id]:
                                return await self.episode(scrape_item, series_id, episode_id)
                            case ["season", season]:
                                return await self.series(scrape_item, series_id, int(season))
                            case _:
                                return await self.series(scrape_item, series_id)
                    case _:
                        raise ValueError
            case _:
                raise ValueError

    @error_handling_wrapper
    async def series(self, scrape_item: ScrapeItem, series_id: str, season: int | None = None) -> None:
        series = await self._series(scrape_item, series_id)
        downloaded = await self.get_album_results(series.id)
        base_url = self.PRIMARY_URL / "on-demand/series" / series.id
        for ep in series.episodes():
            if season is not None and ep.season != season:
                continue

            url = base_url / "season" / str(ep.season) / "episode" / ep.id
            if self.check_album_results(url, downloaded):
                continue

            new_item = scrape_item.create_child(url)
            self.create_task(self._episode(new_item, ep))
            scrape_item.add_children()

    async def _series(self, scrape_item: ScrapeItem, series_id: str) -> Series:
        series = await self.api.series(series_id)
        scrape_item.setup_as_album(self.create_title(series.name, series.id), album_id=series.id)
        self.create_eager_task(self.write_metadata(scrape_item, series.id, series))
        return series

    @error_handling_wrapper
    async def episode(self, scrape_item: ScrapeItem, series_id: str, episode_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        series = await self._series(scrape_item, series_id)
        try:
            episode = next(e for e in series.episodes() if e.id == episode_id)
        except StopIteration:
            raise ScrapeError(404) from None

        await self._episode(scrape_item, episode)

    @error_handling_wrapper
    async def _episode(self, scrape_item: ScrapeItem, ep: Episode) -> None:
        m3u8_url = _compose_stream_url(self.api.stitcher, ep.stitched)
        m3u8, info = await self.request_m3u8_playlist(m3u8_url)
        _remove_ads_segments(m3u8)
        filename = self.create_custom_filename(
            compose_ep_name(ep.season, ep.number, ep.name),
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
            ep.name,
            ext,
            m3u8=m3u8,
            custom_filename=filename,
            metadata=ep,
        )


_STITCHER: ContextVar[Stitcher] = ContextVar("_STITCHER")


class PlutoAPI(API):
    BOOT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://boot.pluto.tv/v4/start")
    FIREFOX: ClassVar[str] = "Mozilla/5.0 (X11; Linux x86_64; rv:151.0) Gecko/20100101 Firefox/151.0"

    def __post_init__(self) -> None:
        self._device_version: str = "151.0.0"  # from firefox's UA
        self._client_id: str = str(uuid.uuid4())

    def __repr__(self) -> str:
        return f"<{type(self).__name__}(app_version={self.app_version.get()}, client_id={self._client_id}, device_version={self._device_version})>"

    @property
    def stitcher(self) -> Stitcher:
        return _STITCHER.get()

    @cached_method()
    async def app_version(self) -> str:
        soup = await self.request_soup(self.PRIMARY_URL)
        return css.select(soup, "meta[name=appVersion]", "content")

    async def boot(self, **params: Any) -> dict[str, Any]:
        url = self.BOOT.with_query(
            appName="web",
            appVersion=await self.app_version(),
            deviceVersion=self._device_version,
            deviceModel="web",
            deviceMake="firefox",
            deviceType="web",
            clientID=self._client_id,
            clientModelNumber="1.0.0",
            serverSideAds="false",
            **params,
        )
        return await self.request_json(url, headers={"User-Agent": self.FIREFOX})

    async def media(self, media_id: str) -> dict[str, Any]:
        boot = await self.boot(seriesIDs=media_id)
        try:
            media = next(v for v in boot.get("VOD", ()) if v["id"] == media_id)
        except StopIteration:
            boot = await self.boot(seriesIDs=media_id, drmCapabilities="widevine:L1")
            has_drm = next((v for v in boot.get("VOD", ()) if v["id"] == media_id), None) is not None
            raise ScrapeError("DRM protected" if has_drm else 404) from None

        _STITCHER.set(
            Stitcher(
                server=self.parse_url(boot["servers"]["stitcher"]),
                params=boot["stitcherParams"],
                token=boot["sessionToken"],
            )
        )
        return media

    async def series(self, series_id: str) -> Series:
        media = await self.media(series_id)
        return deserialize(Series, media)


def _compose_stream_url(stitcher: Stitcher, path: str) -> AbsoluteHttpURL:
    return (
        (stitcher.server / f"v2{path}")
        .update_query(stitcher.params)
        .update_query(
            jwt=stitcher.token,
            includeExtendedEvents="true",
            masterJWTPassthrough="true",
        )
    )


@dataclasses.dataclass(slots=True)
class Stitcher:
    server: AbsoluteHttpURL
    params: str
    token: str


class Season(TypedDict):
    number: int
    episodes: list[dict[str, Any]]


@dataclasses.dataclass(slots=True, order=True)
class Media:
    id: str
    name: str
    description: str
    slug: str
    rating: str | None
    genre: str


@dataclasses.dataclass(slots=True)
class Episode(Media):
    season: int
    number: int
    duration: int
    stitched: str


@dataclasses.dataclass(slots=True)
class Series(Media):
    seasons: list[Season] = dataclasses.field(default_factory=list)

    def episodes(self) -> Generator[Episode]:
        for season in self.seasons:
            for ep in season["episodes"]:
                yield deserialize(
                    Episode,
                    ep,
                    id=ep.get("id") or ep["_id"],
                    stitched=ep["stitched"]["path"],
                )


def _remove_ads_segments(rendition: Rendition) -> None:
    for m3u8 in rendition:
        if not m3u8:
            continue

        m3u8.data["segments"] = [s for s in m3u8.data["segments"] if not _is_ad(s["uri"])]
        m3u8._initialize_attributes()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]


def _is_ad(uri: str) -> bool:
    path = yarl.URL(uri).path.casefold()
    return any(ad_name in path for ad_name in ("_ad%2f", "_ad/", "_ad_bumper", "plutotv_filler"))
