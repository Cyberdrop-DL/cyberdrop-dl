from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.mediaprops import Subtitle
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


@dataclasses.dataclass(slots=True)
class Video:
    title: str
    uploaded_at: float
    src: AbsoluteHttpURL
    thumbnail: AbsoluteHttpURL


@Crawler.db_path_builder("url")
class RedditMediaCrawler(Crawler):
    # Only support videos. let the generic crawler download images
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Video": "v.redd.it/<video_id>"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://v.redd.it")
    DOMAIN: ClassVar[str] = "v.redd.it"
    FOLDER_DOMAIN: ClassVar[str] = "Reddit"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [video_id]:
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        m3u8_url = self.PRIMARY_URL / video_id / "HLSPlaylist.m3u8"
        if await self.check_complete(m3u8_url):
            return

        m3u8, info = await self.request_m3u8_playlist(m3u8_url)
        filename = self.create_custom_filename(
            video_id,
            ext := ".mp4",
            resolution=info and info.resolution,
            video_codec=info and info.codecs.video,
            audio_codec=info and info.codecs.audio,
        )
        await self.handle_file(m3u8_url, scrape_item, video_id, ext, m3u8=m3u8, custom_filename=filename)
        self.handle_subs(scrape_item, filename, [Subtitle(m3u8_url.with_name("wh_ben_en.vtt"), lang_code="en")])
