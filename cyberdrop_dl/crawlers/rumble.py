from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.mediaprops import Resolution, Subtitle
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class RumbleCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "<video_id>-<video-title>.html",
        "Embed": "/embed/<video_id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://rumble.com")
    DOMAIN: ClassVar[str] = "rumble"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["embed", video_id] if video_id.startswith("v"):
                return await self.embed(scrape_item, video_id)
            case [slug] if slug.startswith("v") and slug.endswith(".html"):
                return await self.video(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        embed_id = self.parse_url(css.get_json_ld_value(soup, "embedUrl")).name
        await self.embed(scrape_item, embed_id)

    @error_handling_wrapper
    async def embed(self, scrape_item: ScrapeItem, embed_id: str) -> None:
        api_url = (self.PRIMARY_URL / "embedJS/u3").with_query(request="video", ver=2, v=embed_id)
        video = _parse_video(await self.request_json(api_url))
        link = self.parse_url(video.format.url)
        _, ext = self.get_filename_and_ext(link.name)
        custom_filename = self.create_custom_filename(
            video.title, ext, file_id=embed_id, resolution=video.format.resolution
        )
        scrape_item.possible_datetime = self.parse_iso_date(video.upload_date)
        scrape_item.url = self.parse_url(video.url)
        self.create_task(self.handle_file(link, scrape_item, link.name, ext, custom_filename=custom_filename))
        self.handle_subs(scrape_item, custom_filename, video.subtitles)


@dataclasses.dataclass(slots=True, frozen=True)
class Video:
    upload_date: str
    title: str
    format: Format
    subtitles: list[Subtitle]
    url: str


class Format(NamedTuple):
    resolution: Resolution
    bitrate: int
    url: str


def _parse_video(video: dict[str, Any]) -> Video:
    if video.get("live"):
        raise ScrapeError(422, "live videos are not supported")

    formats: dict[str, dict[str, dict[str, Any]]] = video.get("ua") or {}
    subs: dict[str, dict[str, str]] = video.get("cc") or {}

    def parse_formats():
        for name, format_options in formats.items():
            if name in ("tar", "hls"):
                continue

            for format in format_options.values():
                meta: dict[str, Any] = format["meta"]
                resolution = Resolution(meta["w"], meta["h"])
                yield Format(resolution, meta["bitrate"], format["url"])

    def parse_subs():
        for lang_code, sub_info in subs.items():
            if url := sub_info.get("path"):
                yield Subtitle(url, lang_code)

    return Video(
        upload_date=video["pubDate"],
        title=video["title"],
        format=max(parse_formats()),
        subtitles=list(parse_subs()),
        url=video["l"],
    )
