from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text, js_unpacker, open_graph
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class StreamFileCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Video": "/<video_id>.html"}
    DOMAIN: ClassVar[str] = "streamfile"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://streamfile.net")

    def __post_init__(self) -> None:
        self.api: StreamFileAPI = StreamFileAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [slug] if slug.endswith(suffix := ".html"):
                video_id = slug.removesuffix(suffix)
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        video = await self.api.video(video_id)
        m3u8, info = await self.request_m3u8_playlist(video.m3u8)
        await self.handle_file(
            scrape_item.url,
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


class StreamFileAPI(API):
    async def video(self, video_id: str) -> Video:
        soup = await self.request_soup(self.PRIMARY_URL / f"{video_id}.html")
        player = js_unpacker.unpack(js_unpacker.find(soup))
        return Video(
            id=video_id,
            title=css.select_text(soup, "h1"),
            m3u8=self.parse_url(extr_text(player, "var plyrHlsSrc='", "'")),
            thumb=self.parse_url(open_graph.image(soup)),
        )
