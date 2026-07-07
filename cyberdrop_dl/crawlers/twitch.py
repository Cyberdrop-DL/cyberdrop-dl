from __future__ import annotations

import base64
import dataclasses
import json
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.mediaprops import Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import parse_url
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping

    from cyberdrop_dl.url_objects import ScrapeItem
    from cyberdrop_dl.utils import m3u8
    from cyberdrop_dl.utils.m3u8 import M3U8


_CLIPS_URL = AbsoluteHttpURL("https://clips.twitch.tv")
_M3U8_BASE = AbsoluteHttpURL("https://usher.ttvnw.net")


class TwitchCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "VOD": (
            "/video/<vod_id>",
            "?video=<vod_id>",
            "/<user>/v/<vod_id>",
            "/videos/<vod_id>",
        ),
        "Collection": "/collections/<collection_id>",
        "Clip": (
            "/<user>/clip/<slug>",
            "/embed?clip=<slug>",
            "https://clips.twitch.tv/<slug>",
        ),
    }

    DOMAIN: ClassVar[str] = "twitch"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.twitch.tv")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_, "v", video_id]:
                return await self.vod(scrape_item, video_id)
            case ["video" | "videos", video_id]:
                return await self.vod(scrape_item, video_id)
            case ["collections", collection_id]:
                return await self.collection(scrape_item, collection_id)
            case [*_, "clip", slug]:
                await self.clip(scrape_item, slug)
            case ["embed"] if slug := scrape_item.url.query.get("clip"):
                await self.clip(scrape_item, slug)
            case [slug] if "clips." in scrape_item.url.host:
                await self.clip(scrape_item, slug)
            case _:
                if video_id := scrape_item.url.query.get("video"):
                    return await self.vod(scrape_item, video_id)
                if slug := scrape_item.url.query.get("clip"):
                    return await self.clip(scrape_item, slug)

                raise ValueError

    def __post_init__(self) -> None:
        self.api: TwitchAPI = TwitchAPI.from_crawler(self)

    async def _request_m3u8(
        self,
        url: AbsoluteHttpURL,
        /,
        headers: Mapping[str, str] | None = None,
        media_type: Literal["video", "audio", "subtitle"] | None = None,
    ) -> m3u8.M3U8:
        m3u8_obj = await super()._request_m3u8(url, headers=headers, media_type=media_type)

        # Some formats are "hidden" unless the user is logged in (1080p+ resolutions)
        # We can extract and parse them manually, bypassing the logging requirement
        for data in m3u8_obj.session_data:
            if data.data_id == "com.amazon.ivs.unavailable-media" and data.value:
                unavailable_media = json.loads(base64.b64decode(data.value))
                _parse_unavailable_media(m3u8_obj, unavailable_media)
                break

        return m3u8_obj

    @error_handling_wrapper
    async def vod(self, scrape_item: ScrapeItem, video_id: str) -> None:
        video_id = video_id.removeprefix("v")
        scrape_item.url = self.PRIMARY_URL / "videos" / video_id
        if await self.check_complete_from_referer(scrape_item.url):
            return

        video = await self.api.video(video_id)
        date: str | None = video.get("publishedAt")
        if not date:
            raise ScrapeError(422, "Lives are not supported")

        scrape_item.uploaded_at = self.parse_iso_date(date)
        title = video.get("title") or "video"
        access_token = await self.api.access_token(video_id)
        m3u8_url = (_M3U8_BASE / f"vod/{video_id}.m3u8").with_query(
            allow_source="true",
            allow_spectre="true",
            allow_audio_only="false",
            include_unavailable="true",
            platform="web",
            player="twitchweb",
            playlist_include_framerate="true",
            sig=access_token["signature"],
            supported_codecs="av1,h265,h264",
            token=access_token["value"],
        )

        m3u8, info = await self.request_m3u8_playlist(m3u8_url)
        fps = info.stream_info.frame_rate
        filename = self.create_custom_filename(
            title,
            ".mp4",
            file_id=video_id,
            resolution=info.resolution,
            video_codec=info.codecs.video,
            audio_codec=f"{round(fps)}fps" if fps and fps > 45 else None,
        )
        await self.handle_file(m3u8_url, scrape_item, title, m3u8=m3u8, custom_filename=filename)

    @error_handling_wrapper
    async def collection(self, scrape_item: ScrapeItem, collection_id: str) -> None:
        collection = await self.api.collection(collection_id)
        title = self.create_title(collection["title"], collection_id)
        scrape_item.setup_as_album(title, album_id=collection_id)

        for edge in collection["items"]["edges"]:
            web_url = self.PRIMARY_URL / "videos" / edge["node"]["id"]
            self.create_task(self.run(scrape_item.create_child(web_url)))
            scrape_item.add_children()

    @error_handling_wrapper
    async def clip(self, scrape_item: ScrapeItem, slug: str) -> None:
        scrape_item.url = _CLIPS_URL / slug
        if await self.check_complete_from_referer(scrape_item.url):
            return

        clip = await self.api.clip(slug)
        title: str = clip.get("title") or "clip"
        scrape_item.uploaded_at = self.parse_iso_date(clip["createdAt"])
        access_token: dict[str, str] = clip["playbackAccessToken"]

        best = max(ClipFormat.parse(clip["assets"][0]))
        filename = self.create_custom_filename(
            title,
            ".mp4",
            file_id=slug,
            resolution=best.resolution,
            audio_codec=f"{round(best.fps)}fps" if best.fps > 45 else None,
        )
        source = best.url.update_query(token=access_token["value"], sig=access_token["signature"])
        await self.handle_file(source, scrape_item, title, custom_filename=filename)


class TwitchAPI(API):
    """GraphQL API interface for twitch"""

    GQL_ENDPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://gql.twitch.tv/gql")
    CLIENT_ID: ClassVar[str] = "kimne78kx3ncx6brgo4mv6wki5h1ko"

    @classmethod
    def _prepare_query(cls, name: str, variables: dict[str, Any], query_hash: str) -> dict[str, Any]:
        return {
            "operationName": name,
            "variables": variables,
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": query_hash,
                }
            },
        }

    async def _request_many(self, queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return await self.request_json(
            self.GQL_ENDPOINT,
            method="POST",
            headers={
                "Content-Type": "text/plain;charset=UTF-8",
                "Client-ID": self.CLIENT_ID,
            },
            json=queries,
        )

    async def _request(self, name: str, variables: dict[str, Any], query_hash: str) -> dict[str, Any]:
        """Simplified version to make a single query request"""
        query = self._prepare_query(name, variables, query_hash)
        return (await self._request_many([query]))[0]

    async def video(self, video_id: str) -> dict[str, Any]:
        resp = await self._request(
            "VideoMetadata",
            {
                "channelLogin": "",
                "videoID": video_id,
            },
            "45111672eea2e507f8ba44d101a61862f9c56b11dee09a15634cb75cb9b9084d",
        )
        video = resp["data"]["video"]
        if video is None:
            raise ScrapeError(404)
        return video

    async def collection(self, collection_id: str) -> dict[str, Any]:
        resp = await self._request(
            "CollectionSideBar",
            {
                "collectionID": collection_id,
            },
            "016e1e4ccee0eb4698eb3bf1a04dc1c077fb746c78c82bac9a8f0289658fbd1a",
        )
        col = resp["data"]["collection"]
        if col is None:
            raise ScrapeError(404)
        return col

    async def clip(self, slug: str) -> dict[str, Any]:
        resp = await self._request(
            "ShareClipRenderStatus",
            {
                "slug": slug,
            },
            "0a02bb974443b576f5579aab0fef1d4b7f44e58a8a256f0c5adfead0db70640f",
        )
        clip = resp["data"]["clip"]
        if clip is None:
            raise ScrapeError(404)
        return clip

    async def access_token(self, video_id: str) -> dict[str, str]:
        resp = await self._request(
            "PlaybackAccessToken",
            {
                "isLive": False,
                "login": "",
                "isVod": True,
                "vodID": video_id,
                "playerType": "site",
                "platform": "web",
            },
            "ed230aa1e33e07eebb8928504583da78a5173989fadfb1ac94be06a04f3cdbe9",
        )
        return resp["data"]["videoPlaybackAccessToken"]


@dataclasses.dataclass(slots=True, order=True, frozen=True)
class ClipFormat:
    resolution: Resolution
    fps: float
    aspect_ratio: float
    url: AbsoluteHttpURL

    @staticmethod
    def parse(assets: dict[str, Any]) -> Generator[ClipFormat]:
        for fmt in assets["videoQualities"]:
            yield ClipFormat(
                url=parse_url(fmt["sourceURL"]),
                fps=fmt["frameRate"],
                resolution=Resolution.parse(fmt["quality"]),
                aspect_ratio=assets["aspectRatio"],
            )


def _parse_unavailable_media(m3u8: M3U8, hidden_media: list[dict[str, Any]]) -> None:
    first_rendition = parse_url(m3u8.playlists[0].absolute_uri)
    base_url, filename = first_rendition.parent.parent, first_rendition.name

    for media in hidden_media:
        if not media["RESOLUTION"]:
            continue

        m3u8.data["playlists"].append(
            {
                "uri": str(base_url / media["GROUP-ID"] / filename),
                "stream_info": {
                    "bandwidth": media["BANDWIDTH"],
                    "codecs": media["CODECS"],
                    "resolution": media["RESOLUTION"],
                    "video": media["GROUP-ID"],
                    "frame_rate": media["FRAME-RATE"],
                },
            }
        )
        m3u8.data["media"].append(
            {
                "type": "VIDEO",
                "group_id": media["GROUP-ID"],
                "name": media["NAME"],
                "autoselect": "YES",
                "default": "YES",
            }
        )
    m3u8._initialize_attributes()  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
