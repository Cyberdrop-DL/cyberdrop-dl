from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.mediaprops import Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper, extr_text, open_graph, parse_url

if TYPE_CHECKING:
    from collections.abc import Generator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


@dataclasses.dataclass(frozen=True, slots=True)
class Video:
    title: str
    resolution: Resolution
    src: AbsoluteHttpURL


class YouJizzCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/videos/embed/<video_id>",
            "/videos/<video_name>",
        )
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.youjizz.com/")
    DOMAIN: ClassVar[str] = "youjizz"
    FOLDER_DOMAIN: ClassVar[str] = "YouJizz"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["videos", "embed", video_id]:
                return await self.video(scrape_item, video_id)
            case ["videos", video_name]:
                video_id = video_name.rsplit("-", 1)[-1].removesuffix(".html")
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        canonical_url = self.PRIMARY_URL / "videos" / "embed" / video_id
        if await self.check_complete_from_referer(canonical_url):
            return

        soup = await self.request_soup(scrape_item.url)
        scrape_item.url = canonical_url
        video = _parse_video(soup)
        filename, ext = self.get_filename_and_ext(video.src.name)
        custom_filename = self.create_custom_filename(
            video.title,
            ext,
            file_id=video_id,
            resolution=video.resolution,
        )
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            filename,
            ext,
            custom_filename=custom_filename,
            debrid_link=video.src,
        )


def _parse_video(soup: BeautifulSoup) -> Video:
    js_text = css.select_text(soup, "script:-soup-contains('var dataEncodings')")
    encodings_text = extr_text(js_text, "var dataEncodings =", "var encodings").removesuffix(";")
    data_encodings = json.loads(encodings_text)
    res, src = max(_parse_formats(data_encodings))
    return Video(resolution=res, src=src, title=open_graph.title(soup))


def _parse_formats(data_encodings: list[dict[str, Any]]) -> Generator[tuple[Resolution, AbsoluteHttpURL]]:
    for fmt in data_encodings:
        if "/_hls/" in fmt["filename"]:
            continue

        url = parse_url(fmt["filename"])
        if url.suffix == ".m3u8":
            continue

        res = Resolution.parse(int(fmt["quality"]))
        yield res, url
