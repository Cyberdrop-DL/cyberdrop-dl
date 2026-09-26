from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, Final, Self, override

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.models import type_adapter
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from cyberdrop_dl.url_objects import ScrapeItem


class KickCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Clip": (
            "/<channel>/clip/clip_<clip_id>",
            "/<channel>?clip=clip_<clip_id>",
        ),
        "VOD": ("/<channel>/videos/<vod_uuid>",),
        "Channel videos": "/<channel>/videos",
        "Channel clips": "/<channel>/clips?sort=...&range=...",
    }
    DOMAIN: ClassVar[str] = "kick"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://kick.com")

    def __post_init__(self) -> None:
        self.api: KickAPI = KickAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_, "clips", clip_id] if clip_id.startswith("clip_"):
                await self.clip(scrape_item, clip_id)
            case [_, "videos", vod_uuid]:
                await self.vod(scrape_item, vod_uuid)
            case [channel, "clips"]:
                await self.clips(scrape_item, channel)
            case [channel, "videos"]:
                await self.videos(scrape_item, channel)
            case _:
                raise ValueError

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case [user] if (clip_id := url.query.get("clip")) and clip_id.startswith("clip_"):
                return url.origin() / user / "clips" / clip_id
            case _:
                return url

    @error_handling_wrapper
    async def clip(self, scrape_item: ScrapeItem, clip_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        clip = await self.api.clip(clip_id)
        await self._video(scrape_item, clip)

    @error_handling_wrapper
    async def vod(self, scrape_item: ScrapeItem, vod_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        vod = await self.api.vod(vod_id)
        await self._video(scrape_item, vod)

    async def _video(self, scrape_item: ScrapeItem, clip: Clip) -> None:
        scrape_item.setup_as_profile(self.create_title(clip.channel.username))
        scrape_item.uploaded_at = self.parse_iso_date(clip.created_at)
        src = clip.playback_url
        if src.suffix == ".m3u8":
            m3u8, info = await self.request_m3u8(src)
        else:
            m3u8 = info = None

        await self.handle_file(
            src if "db" in src.parts else scrape_item.url,
            scrape_item,
            clip.title,
            ext := ".mp4",
            custom_filename=self.create_custom_filename(
                clip.title,
                ext,
                file_id=clip.id,
                resolution=info and info.resolution,
                video_codec=info and info.codecs.video,
                audio_codec=info and info.codecs.audio,
            ),
            m3u8=m3u8,
            thumbnail=clip.thumbnail_url,
        )

    @error_handling_wrapper
    async def clips(self, scrape_item: ScrapeItem, channel_name: str) -> None:
        scrape_item.setup_as_profile("")
        channel = await self.api.channel(channel_name)
        async for clips in self.api.channel.clips(channel.id, scrape_item.url.query):
            async with self.new_task_group() as tg:
                for clip in clips:
                    new_item = scrape_item.create_child(scrape_item.url / clip.id)
                    tg.create_task(self.clip_task(new_item, clip))
                    scrape_item.add_children()

    @error_handling_wrapper
    async def clip_task(self, scrape_item: ScrapeItem, clip: Clip) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        await self._video(scrape_item, clip)

    @error_handling_wrapper
    async def videos(self, scrape_item: ScrapeItem, channel_name: str) -> None:
        scrape_item.setup_as_profile("")
        channel = await self.api.channel(channel_name)
        videos = await self.api.channel.videos(channel.id)
        async with self.new_task_group() as tg:
            for vod in videos:
                new_item = scrape_item.create_child(scrape_item.url / vod.id)
                tg.create_task(self.vod_task(new_item, vod))
                scrape_item.add_children()

    @error_handling_wrapper
    async def vod_task(self, scrape_item: ScrapeItem, meta: VODMetadata) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        video = await self.api.vod.resolve(meta)
        await self._video(scrape_item, video)


@dataclasses.dataclass(slots=True, frozen=True)
class Video:
    id: str
    title: str
    m3u8: AbsoluteHttpURL
    thumb: AbsoluteHttpURL


class KickAPI(API):
    V1: Final = AbsoluteHttpURL("https://web.kick.com/api/v1")
    V2: Final = AbsoluteHttpURL("https://kick.com/api/v2")

    def __post_init__(self) -> None:
        self.channel: ChannelEndpoint = ChannelEndpoint(self)
        self.vod: VODEndpoint = VODEndpoint(self)

    async def clip(self, clip_id: str) -> Clip:
        url = self.V2 / "clips" / clip_id
        resp = await self.request_json(url)
        return Clip.parse(resp["clip"])

    async def pager(self, url: AbsoluteHttpURL, query: Mapping[str, str]) -> AsyncGenerator[dict[str, Any]]:
        url = url.update_query(_filter_pag_query(query))
        while True:
            data = (await self.request_json(url))["data"]
            yield data
            cursor = data.get("cursor")
            if not cursor:
                return
            url = url.update_query(cursor=cursor)


class VODEndpoint(API.Endpoint[KickAPI]):
    async def __call__(self, vod_uuid: str) -> Clip:
        creator_id, playback = await self.playback(vod_uuid)
        meta = await self.metadata(creator_id, vod_uuid)
        return Clip(
            id=meta.id,
            title=meta.title,
            thumbnail_url=meta.thumbnail_url,
            created_at=meta.start_time,
            channel=meta.channel,
            playback_url=playback,
        )

    async def playback(self, vod_uuid: str) -> tuple[str, AbsoluteHttpURL]:
        url = self.api.V1 / "stream" / vod_uuid / "playback"
        playback = await self.api.request_json(
            url,
            "POST",
            json={
                "video_player": {
                    "player": {
                        "player_name": "web_mobile",
                        "player_software": "IVS Player",
                        "player_software_version": "1.56.0",
                        "player_version": "web_mobile",
                    }
                },
                "video_session": {},
                "user_session": {
                    "browser_lang": "en",
                    "non_personalised_ads": True,
                },
            },
        )
        return playback["video_session"]["creator_id"], self.api.parse_url(playback["playback_url"]["vod"])

    async def resolve(self, meta: VODMetadata) -> Clip:
        _, playback = await self.playback(meta.id)
        return Clip(
            id=meta.id,
            title=meta.title,
            thumbnail_url=meta.thumbnail_url,
            created_at=meta.start_time,
            channel=meta.channel,
            playback_url=playback,
        )

    async def metadata(self, creator_id: str, vod_uuid: str) -> VODMetadata:
        url = self.api.V1 / "channels" / creator_id / "videos" / vod_uuid
        vod: dict[str, Any] = (await self.api.request_json(url))["data"]
        if vod.get("is_live"):
            raise ScrapeError(422, "Livestreams are not supported")

        return VODMetadata.parse(vod)


class ChannelEndpoint(API.Endpoint[KickAPI]):
    def __post_init__(self) -> None:
        self._channels: dict[str, User] = {}
        self._channel_locks: aio.WeakAsyncLocks[str] = aio.WeakAsyncLocks()

    async def __call__(self, slug: str) -> User:
        slug = slug.lower()
        try:
            return self._channels[slug]
        except LookupError:
            pass

        async with self._channel_locks[slug]:
            try:
                return self._channels[slug]
            except LookupError:
                pass

            url = self.api.V2 / "channels" / slug
            resp = await self.api.request_json(url)
            resp["username"] = resp["user"]["username"]
            self._channels[slug] = user = type_adapter(User).validate_python(resp)
            return user

    async def clips(self, channel_id: int, query: Mapping[str, str]) -> AsyncGenerator[map[Clip]]:
        url = self.api.V1 / f"channels/{channel_id}/clips"
        async for resp in self.api.pager(url, query):
            yield map(Clip.parse, resp["clips"])

    async def videos(self, channel_id: int) -> map[VODMetadata]:
        # This endpoint has no pagination
        url = self.api.V1 / f"channels/{channel_id}/videos"
        data = (await self.api.request_json(url))["data"]
        return map(VODMetadata.parse, (v for v in data if not v.get("is_live")))


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class Clip:
    id: str
    title: str
    thumbnail_url: AbsoluteHttpURL
    created_at: str
    playback_url: AbsoluteHttpURL
    channel: User

    @classmethod
    def parse(cls, clip: dict[str, Any]) -> Self:
        clip["playback_url"] = clip.get("clip_url") or clip.get("video_url") or clip["playback_url"]
        return type_adapter(cls).validate_python(clip)


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True)
class VODMetadata:
    id: str
    title: str
    start_time: str
    status: str
    thumbnail_url: AbsoluteHttpURL
    channel: User

    @classmethod
    def parse(cls, vod: dict[str, Any]) -> Self:
        vod["thumbnail_url"] = css.best_from_srcset(vod["thumbnail"]["srcSet"])
        return type_adapter(cls).validate_python(vod)


@dataclasses.dataclass(kw_only=True, frozen=True, slots=True, order=True)
class User:
    id: int
    slug: str
    username: str


def _filter_pag_query(query: Mapping[str, str]) -> dict[str, str]:
    sort, time = map(query.get, ("sort", "range"))
    sort = sort if sort in {"view", "views", "date"} else "views"
    return {
        "sort": "views" if sort == "view" else sort,
        "time": time if time in {"day", "week", "month", "all"} else "week",
    }
