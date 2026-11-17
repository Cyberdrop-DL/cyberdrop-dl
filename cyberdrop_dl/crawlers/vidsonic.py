from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import API, Crawler, DownloadConfig, SupportedDomains, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import b64_pad, css, extr_text, open_graph
from cyberdrop_dl.utils.dataclass import struct
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


@DownloadConfig(slots=2)
class VidSonicCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = ("vidsonic.net", "vixeo.io", "vsonic.click")
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/e/<video_id>",
            "/d/<video_id>",
        ),
    }
    DOMAIN: ClassVar[str] = "vidsonic"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vidsonic.net")

    def __post_init__(self) -> None:
        self.api: VidSonicAPI = VidSonicAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["e" | "d", video_id]:
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        embed_url = self.PRIMARY_URL / "e" / video_id
        if await self.check_complete(embed_url):
            return

        video = await self.api.video(video_id)
        m3u8, info = await self.request_m3u8_playlist(
            video.m3u8, headers={"Referer": str(scrape_item.get_referer() or scrape_item.url)}
        )
        await self.handle_file(
            embed_url,
            scrape_item,
            video.title,
            ext := ".mp4",
            m3u8=m3u8,
            custom_filename=self.create_custom_filename(video.title, ext, file_id=video_id, resolution=info.resolution),
            thumbnail=video.thumb,
        )


@struct
class Video:
    id: str
    title: str
    m3u8: AbsoluteHttpURL
    thumb: AbsoluteHttpURL


class VidSonicAPI(API):
    async def video(self, video_id: str) -> Video:
        async with self.request(self.PRIMARY_URL / "e" / video_id) as resp:
            html = await resp.html()
            soup = await resp.soup()

        try:
            config = css.select(soup, "[data-config]", "data-config")
        except css.SelectorError:
            src = extr_text(html, "const _0x1 = '", "'")
        else:
            src = json.loads(base64.b64decode(b64_pad(config)))["source"]

        src = bytes.fromhex(src.replace("|", "")).decode()[::-1]

        return Video(
            id=video_id,
            title=open_graph.title(soup),
            m3u8=self.parse_url(src),
            thumb=self.parse_url(open_graph.image(soup)),
        )
