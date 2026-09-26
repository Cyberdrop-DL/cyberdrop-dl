from __future__ import annotations

import asyncio
import dataclasses
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text, js_unpacker
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator

    import bs4

    from cyberdrop_dl.url_objects import ScrapeItem


class RecordPlayCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/e/<video_id>",
            "/d/<video_id>",
        ),
    }
    DOMAIN: ClassVar[str] = "recordplay"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://recordplay.biz")

    def __post_init__(self) -> None:
        self.api: RecordPlayAPI = RecordPlayAPI.from_crawler(self)

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


class RecordPlayAPI(API):
    async def video(self, video_id: str) -> Video:
        soup = await self.request_soup(self.PRIMARY_URL / "e" / video_id)
        src = await asyncio.to_thread(_extract_src, soup)

        return Video(
            id=video_id,
            title=css.select_text(soup, "title"),
            m3u8=self.parse_url(src),
            thumb=self.parse_url(css.select(soup, "#vplayer img", "src")),
        )


def _extract_src(soup: bs4.Tag) -> str:
    player = js_unpacker.unpack(js_unpacker.find(soup))
    sources = dict(sorted(_extract_sources(player), reverse=True))
    if not sources:
        raise ScrapeError(422, "No stream source found")

    return next(iter(sources.values()))


def _extract_sources(player: str) -> Generator[tuple[str, str]]:
    for link in extr_text(player, "var links={", "};").split('","'):
        name, _, src = link.partition(":")
        yield name.strip('"'), src.strip('"')
