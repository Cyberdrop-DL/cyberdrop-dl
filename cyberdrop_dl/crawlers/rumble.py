from __future__ import annotations

import dataclasses
import itertools
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple

from cyberdrop_dl.compat import IntEnum
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.mediaprops import Resolution, Subtitle
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.exceptions import DownloadError, ScrapeError
from cyberdrop_dl.utils import aio, css, m3u8
from cyberdrop_dl.utils.utilities import error_handling_wrapper, parse_url

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class LiveStatus(IntEnum):
    NOT_LIVE = 0
    LIVE_ENDED = 1
    CURRENTLY_LIVE = 2


class FormatType(IntEnum):
    HLS = 1
    WEBM = 2
    MP4 = 3


class Metadata(NamedTuple):
    bitrate: int = 0
    size: int = 0
    w: int = 0
    h: int = 0


class Format(NamedTuple):
    resolution: Resolution
    is_single_file: bool  # for formats with the same resolution, give priority to non hls
    bitrate: int
    size: int
    type: FormatType  #  On formats where everything else is the same, choose mp4 over webm
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
    def parse_formats(formats: dict[str, list[dict[str, Any]] | dict[str, dict[str, Any]]]) -> Generator[Format]:
        for type_, format_options in formats.items():
            if type_ in ("audio", "tar", "timeline"):
                continue

            try:
                type_ = FormatType[type_.upper()]
            except KeyError:
                raise ScrapeError(422, f"Video has an unknown format type: {type_}") from None

            if isinstance(format_options, list):
                pairs = ((None, f) for f in format_options)
            else:
                pairs = format_options.items()

            is_single_file = type_ is not FormatType.HLS

            for height, format in pairs:
                url = parse_url(format["url"])
                meta = Metadata(**(format.get("meta") or {}))

                if meta.w and meta.h:
                    resolution = Resolution(meta.w, meta.h)

                elif height and height != "auto":
                    resolution = Resolution.parse(height)

                else:
                    resolution = Resolution.unknown()

                yield Format(resolution, is_single_file, meta.bitrate, meta.size, type_, url)

    @staticmethod
    def parse_subs(subs: dict[str, dict[str, str]]) -> Generator[Subtitle]:
        for code, sub in subs.items():
            yield Subtitle(
                url=sub["path"],
                lang_code=code.replace("-auto", ".auto"),
                name=sub.get("language"),
            )


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
            case ["c" | "user", user_name, *_]:
                return await self.channel(scrape_item, user_name)
            case _:
                raise ValueError

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        match url.parts[1:]:
            case [slug] if slug.startswith("v") and slug.endswith(".html"):
                return url.with_query(None)
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
        best_format = video.best_format
        if best_format.m3u8:
            ext = ".mp4"
        else:
            _, ext = self.get_filename_and_ext(best_format.url.name)

        video_name = self.create_custom_filename(video.title, ext, file_id=embed_id, resolution=best_format.resolution)
        scrape_item.possible_datetime = self.parse_iso_date(video.upload_date)
        scrape_item.url = video.url
        self.create_task(
            self.handle_file(
                best_format.url,
                scrape_item,
                f"{video.title}{ext}",
                ext,
                custom_filename=video_name,
                m3u8=best_format.m3u8,
            )
        )
        self.handle_subs(scrape_item, video_name, video.subtitles)

    async def _get_video_info(self, embed_id: str) -> Video:
        api_url = (self.PRIMARY_URL / "embedJS/u3").with_query(request="video", ver=2, v=embed_id)
        video: dict[str, Any] = await self.request_json(api_url)

        if video.get("live") == LiveStatus.CURRENTLY_LIVE:
            raise ScrapeError(422, "livestreams are not supported")

        formats = Video.parse_formats(video.get("ua") or {})
        subs = Video.parse_subs(video.get("cc") or {})

        return Video(
            upload_date=video["pubDate"],
            title=css.unescape(video["title"]),
            url=self.parse_url(video["l"]),
            best_format=await self._get_best_format(formats),
            subtitles=tuple(subs),
        )

    async def _get_best_format(self, formats: Iterable[Format]) -> Format:
        hls_formats: list[Format] = []
        other_formats: list[Format] = [fmt for fmt in formats if fmt.is_single_file or hls_formats.append(fmt)]

        async def resolve_m3u8(format: Format) -> Format:
            m3u8, info = await self.get_m3u8_from_playlist_url(format.url)
            return format._replace(
                resolution=info.resolution,
                m3u8=m3u8,
                bitrate=info.stream_info.bandwidth or 0,
            )

        if hls_formats:
            hls_formats = await aio.gather([resolve_m3u8(f) for f in hls_formats])

        return max((*hls_formats, *other_formats))
