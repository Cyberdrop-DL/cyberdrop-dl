from __future__ import annotations

import base64
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, DownloadConfig, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import extr_text
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


@DownloadConfig(slots=2)
class XPorniumCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Video": "/embed/<video_id>"}
    DOMAIN: ClassVar[str] = "xpornium"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://xpornium.net")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["embed", video_id]:
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        text = await self.request_text(scrape_item.url)
        src, thumb = base64.b64decode(extr_text(text, "XPSYS('", "');")).decode(), extr_text(text, 'poster="', '" ')

        await self.handle_file(
            scrape_item.url,
            scrape_item,
            video_id,
            ext := ".mp4",
            custom_filename=self.create_custom_filename(video_id, ext),
            debrid_link=self.parse_url(src),
            thumbnail=self.parse_url(thumb),
        )
