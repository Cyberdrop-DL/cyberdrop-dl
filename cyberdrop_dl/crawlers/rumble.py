from __future__ import annotations

import dataclasses
import itertools
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from bs4 import BeautifulSoup

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.mediaprops import Resolution, Subtitle
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import DownloadError, ScrapeError
from cyberdrop_dl.utils import aio, css, m3u8
from cyberdrop_dl.utils.utilities import error_handling_wrapper, parse_url

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class RumbleCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Channel": "/c/<name>",
        "User": "/user/<name>",
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
            case ["c" | "user", user_name, "videos"]:
                return await self.channel(scrape_item, user_name)
            case _:
                raise ValueError

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        match url.parts[1:]:
            case [slug] if slug.startswith("v") and slug.endswith(".html"):
                return url.with_query(None)
            case ["c" | "user", _]:
                return url / "videos"
            case _:
                return url

    @error_handling_wrapper
    async def channel(self, scrape_item: ScrapeItem, name: str) -> None:
        scrape_item.setup_as_album(self.create_title(name))
        init_page = int(scrape_item.url.query.get("page") or 1)
        try:
            for page in itertools.count(init_page):
                soup = await self.request_soup(scrape_item.url.update_query(page=page))
                for _, new_scrape_item in self.iter_children(scrape_item, soup, "a.videostream__link"):
                    self.create_task(self.run(new_scrape_item))

        except DownloadError as e:
            if e.status == 404:
                return
            raise

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        embed_id = self.parse_url(css.get_json_ld(soup)["embedUrl"]).name
        await self.embed(scrape_item, embed_id)

    @error_handling_wrapper
    async def embed(self, scrape_item: ScrapeItem, embed_id: str) -> None:
        video = await self._get_video_info(embed_id)
        ext = ".mp4"
        video_name = self.create_custom_filename(
            video.title, ext, file_id=embed_id, resolution=video.best_format.resolution
        )
        scrape_item.possible_datetime = self.parse_iso_date(video.upload_date)
        scrape_item.url = video.url
        self.create_task(
            self.handle_file(
                video.best_format.url,
                scrape_item,
                video.best_format.url.name,
                ext,
                custom_filename=video_name,
                m3u8=video.best_format.m3u8,
            )
        )
        self.handle_subs(scrape_item, video_name, video.subtitles)

    async def _get_video_info(self, embed_id: str) -> Video:
        api_url = (self.PRIMARY_URL / "embedJS/u3").with_query(request="video", ver=2, v=embed_id)
        video: dict[str, Any] = await self.request_json(api_url)

        if video.get("live"):
            raise ScrapeError(422, "live videos are not supported")

        formats = Video.parse_formats(video.get("ua") or {})
        subs = Video.parse_subs(video.get("cc") or {})

        return Video(
            upload_date=video["pubDate"],
            title=BeautifulSoup(video["title"]).get_text(),
            url=self.parse_url(video["l"]),
            best_format=await self._get_best_format(formats),
            subtitles=tuple(subs),
        )

    async def _get_best_format(self, formats: Iterable[Format]) -> Format:
        hls_formats: list[Format] = []
        other_formats: list[Format] = []

        for f in formats:
            group = hls_formats if f.type == "hls" else other_formats
            group.append(f)

        if hls_formats:
            hls_formats = await aio.gather([self._resolve_m3u8(f) for f in hls_formats])

        return max(*hls_formats, *other_formats)

    async def _resolve_m3u8(self, format: Format) -> Format:
        resolution = format.resolution
        if resolution != Resolution.unknown():
            m3u8 = await self.get_m3u8_from_index_url(format.url)
        else:
            m3u8, info = await self.get_m3u8_from_playlist_url(format.url)
            resolution = info.resolution

        return Format(resolution, format.type, 0, format.url, m3u8)


@dataclasses.dataclass(slots=True, frozen=True, order=True)
class Format:
    resolution: Resolution
    type: Literal["hls", "mp4", "webm"]  # if resolution is the same, prefer: webm > mp4 > hls
    bitrate: int
    url: AbsoluteHttpURL
    m3u8: m3u8.RenditionGroup | None = None


@dataclasses.dataclass(slots=True, frozen=True)
class Video:
    title: str
    upload_date: str
    url: AbsoluteHttpURL
    best_format: Format
    subtitles: tuple[Subtitle, ...]

    @staticmethod
    def parse_formats(formats: dict[str, dict[str, dict[str, Any]]]) -> Generator[Format]:
        for name, format_options in formats.items():
            if name in ("audio", "tar", "timeline"):
                continue

            if name not in ("hls", "mp4", "webm"):
                raise ScrapeError(422, f"Unknown format type: {name} ()")

            for res, format in format_options.items():
                url = parse_url(format["url"])
                if name == "hls":
                    resolution = Resolution.parse(res) if res != "auto" else Resolution.unknown()
                    yield Format(resolution, name, 0, url)
                    continue

                meta: dict[str, Any] = format["meta"]
                resolution = Resolution(meta["w"], meta["h"])
                yield Format(resolution, name, meta["bitrate"], url)

    @staticmethod
    def parse_subs(subs: dict[str, dict[str, str]]) -> Generator[Subtitle]:
        for lang_code, sub in subs.items():
            if url := sub.get("path"):
                name = sub.get("language")
                yield Subtitle(url, lang_code.removesuffix("-auto"), name)
