from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import API, Crawler, DownloadConfig, SupportedDomains, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


@Crawler.db_path_builder("path_qs_frag")
@DownloadConfig(slots=2)
class VidaraCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = (
        "stmix.io",
        "streamix",
        "thebesthosterv.com",
        "vidara",
        "viderea",
        "vidmatrixa",
        "vidvara",
        "vidwara",
        "viewdara",
        "xca.cymru",
    )
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/e/<video_id>",
            "/v/<video_id>",
        ),
    }
    DOMAIN: ClassVar[str] = "vidara"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vidara.to")

    def __post_init__(self) -> None:
        self.api: VidaraAPI = VidaraAPI.from_crawler(self)

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
        m3u8, info = await self.request_m3u8_playlist(video.m3u8)
        await self.handle_file(
            embed_url,
            scrape_item,
            video.title,
            ext := ".mp4",
            m3u8=m3u8,
            custom_filename=self.create_custom_filename(video.title, ext, file_id=video_id, resolution=info.resolution),
            thumbnail=video.thumb,
        )


@dataclasses.dataclass(slots=True, frozen=True)
class Video:
    id: str
    title: str
    m3u8: AbsoluteHttpURL
    thumb: AbsoluteHttpURL


class VidaraAPI(API):
    async def video(self, video_id: str) -> Video:
        resp = await self.request_json(
            self.PRIMARY_URL / "api/stream",
            method="POST",
            json={
                "device": "web",
                "filecode": video_id,
            },
        )
        title = resp.get("title")
        if not title:
            html = await self.request_text(self.PRIMARY_URL / "e" / video_id)
            title = css.select_tag_text(html, "title")

        return Video(
            id=video_id,
            title=title,
            m3u8=self.parse_url(resp["streaming_url"]),
            thumb=self.parse_url(resp["thumbnail"]),
        )
