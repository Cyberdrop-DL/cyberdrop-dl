from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import TextExtractor, css, js_unpacker
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class LuluStreamCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = (
        "lulustream",
        "luluvdo.com",
        "lulu.st",
        "luluvid.com",
        "cdn1.site",
        "streamhihi.com",
        "luluvdoo.com",
    )
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/e/<video_id>",
            "/d/<video_id>",
            "/<video_id>",
        ),
    }
    DOMAIN: ClassVar[str] = "lulustream"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://lulustream.com")

    def __post_init__(self) -> None:
        self.api: LuluStreamAPI = LuluStreamAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["e" | "d", video_id] | [video_id]:
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


class LuluStreamAPI(API):
    async def video(self, video_id: str) -> Video:
        embed, web = await aio.gather(
            self.request_soup(self.origin / "e" / video_id),
            self.request_soup(self.origin / "d" / video_id),
            fail_fast=False,
        )
        player = js_unpacker.unpack(js_unpacker.find(embed))
        extr = TextExtractor(player)
        return Video(
            id=video_id,
            title=css.select_text(web, "h1"),
            m3u8=self.parse_url(extr('{sources:[{file:"', '"')),
            thumb=self.parse_url(extr('image:"', '"')),
        )
