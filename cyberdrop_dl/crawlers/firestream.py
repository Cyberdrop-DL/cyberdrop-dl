from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class FireStreamCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/e/<video_id>",
            "/v/<video_id>",
        ),
    }
    DOMAIN: ClassVar[str] = "firestream"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://firestream.site")

    def __post_init__(self) -> None:
        self.api: FireStreamAPI = FireStreamAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["e" | "v", video_id]:
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        embed_url = self.PRIMARY_URL / "e" / video_id
        if await self.check_complete(embed_url):
            return

        video = await self.api.video(video_id)
        m3u8_url = await self.api.resolve(video_id, video.token)
        m3u8, info = await self.request_m3u8(m3u8_url)
        _, ext = self.get_filename_and_ext(video.name)
        await self.handle_file(
            embed_url,
            scrape_item,
            video.name,
            ext,
            m3u8=m3u8,
            custom_filename=self.create_custom_filename(
                video.name, ext, file_id=video_id, resolution=info and info.resolution
            ),
            thumbnail=video.thumb,
        )


@dataclasses.dataclass(slots=True, frozen=True)
class Video:
    id: str
    name: str
    token: str
    thumb: AbsoluteHttpURL


class FireStreamAPI(API):
    async def video(self, video_id: str) -> Video:
        url = self.PRIMARY_URL / "e" / video_id
        soup = await self.request_soup(url)
        video = json.loads(css.select_text(soup, "#video-data"))["video"]
        return Video(
            id=video_id,
            name=video.get("originalName") or video["filename"],
            token=css.select_text(soup, "#token-blob"),
            thumb=self.parse_url(video["posterUrl"]),
        )

    async def resolve(self, video_id: str, token: str) -> AbsoluteHttpURL:
        url = self.PRIMARY_URL / "api/videos" / video_id / "resolve"
        resp = await self.request_json(url, "POST", json={"blob": token})
        return self.parse_url(resp["signedVideoUrl"])
