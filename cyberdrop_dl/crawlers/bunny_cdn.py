from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.downloader.bunny_cdn import BunnyCDNDownloader
from cyberdrop_dl.exceptions import DownloadError
from cyberdrop_dl.mediaprops import Subtitle
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.urls import remove_query_params

if TYPE_CHECKING:
    from collections.abc import Generator

    import bs4

    from cyberdrop_dl.url_objects import ScrapeItem


@Crawler.db_path_builder("path_qs")
class BunnyCDNCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/embed/<lib_id>/<video_uuid>",
            "/play/<lib_id>/<video_uuid>",
        ),
    }
    DOMAIN: ClassVar[str] = "bunnycdn"
    FOLDER_DOMAIN: ClassVar[str] = "BunnyCDN"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://iframe.mediadelivery.net")
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = "video.bunnycdn.com", "player.mediadelivery.net"

    downloader: BunnyCDNDownloader

    def __post_init__(self) -> None:
        self.downloader = BunnyCDNDownloader(self.manager, domain=self.FOLDER_DOMAIN)  # pyright: ignore[reportIncompatibleVariableOverride]

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = remove_query_params(super().transform_url(url), keep=("token", "secret"))
        match url.parts[1:]:
            case ["play", _, _]:
                return url.with_path(url.path.replace("/play/", "/embed/"), keep_query=True)
            case _:
                return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["embed", _, video_uuid]:
                await self.video(scrape_item, video_uuid)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        headers = {"Referer": str(scrape_item.get_referer() or self.PRIMARY_URL)}
        html = await self.request_text(scrape_item.url, headers=headers)
        video = await _extract_video(html)
        src, ext, m3u8 = video.src, ".mp4", None
        if video.original:
            try:
                ext = await self.sniff_ext(video.original, headers=headers)
            except DownloadError:
                pass
            else:
                src = video.original

        if src.suffix == ".m3u8":
            m3u8, _ = await self.request_m3u8(src, headers=headers)

        filename = self.create_custom_filename(name := video.title or video_id, ext, file_id=video_id)
        await self.handle_file(
            src,
            scrape_item,
            name,
            ext,
            custom_filename=filename,
            m3u8=m3u8,
            headers=headers,
            thumbnail=video.thumb,
        )
        self.handle_subs(scrape_item, filename, video.subs)


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class Video:
    title: str | None
    thumb: AbsoluteHttpURL
    src: AbsoluteHttpURL
    original: AbsoluteHttpURL | None
    subs: tuple[Subtitle, ...]


def _extract_subs(video: bs4.Tag) -> Generator[Subtitle]:
    for track in css.iselect(video, "track[src]"):
        kind = css.attr_or_none(track, "kind")
        if not kind or kind in {"subtitles", "captions"}:
            yield Subtitle(
                url=css.attr(track, "src"),
                name=css.attr_or_none(track, "label"),
                lang_code=css.attr_or_none(track, "srclang", "lang", "label") or "unk",
            )


@aio.to_thread
def _extract_video(html: str) -> Video:
    video = css.select(css.soup(html, parse_only="video"), "#main-video")
    parse_url = BunnyCDNCrawler.parse_url
    try:
        original = extr_text(html, "originalUrl =", ";").strip("'")
    except ValueError:
        original = None

    try:
        title = json.loads(css.attr(video, "data-plyr-config"))["title"]
    except (ValueError, LookupError, css.SelectorError):
        title = None

    return Video(
        title=title,
        thumb=parse_url(css.attr(video, "data-poster")),
        src=parse_url(css.select(video, "source", "src")),
        original=parse_url(original) if original else None,
        subs=tuple(_extract_subs(video)),
    )
