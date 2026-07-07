from __future__ import annotations

import dataclasses
from collections.abc import Generator
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.dataclass import DictDataclass
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.url_objects import ScrapeItem


_JSON_URL = AbsoluteHttpURL("https://store.externulls.com/facts/file/")
_VIDEO_CDN = AbsoluteHttpURL("https://video.beeg.com/")


@dataclasses.dataclass(slots=True)
class Video:
    title: str
    created_at: str
    mp4_formats: tuple[Format, ...]
    hls_formats: tuple[Format, ...]


@dataclasses.dataclass(slots=True, order=True)
class Format(DictDataclass):
    codec: Literal["h264"]
    quality: int
    average_bandwidth: int
    size: int
    hdr: bool
    url: AbsoluteHttpURL


class BeegComCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/<video_id>",
            "/video/<video_id>",
        )
    }
    DOMAIN: ClassVar[str] = "beeg.com"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://beeg.com/")
    _RATE_LIMIT: ClassVar[RateLimit] = 4, 1

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [video_id]:
                video_id = str(int(video_id.removeprefix("-")))
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["video", video_id]:
                return url.origin() / video_id
            case _:
                return url

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        video = await self._request_video(video_id)
        scrape_item.uploaded_at = self.parse_iso_date(video.created_at)
        best = max(video.hls_formats)
        m3u8, _ = await self.request_m3u8(best.url)
        filename = self.create_custom_filename(
            video.title,
            ext := ".mp4",
            file_id=video_id,
            resolution=best.quality,
        )
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            video.title,
            ext,
            custom_filename=filename,
            m3u8=m3u8,
        )

    async def _request_video(self, video_id: str) -> Video:
        resp: dict[str, Any] = await self.request_json(_JSON_URL / video_id)
        facts: dict[str, Any] = min(resp["fc_facts"], key=lambda x: int(x["id"]))
        file: dict[str, Any] = resp["file"]
        return Video(
            title=next(data for data in file["data"] if data.get("cd_column") == "sf_name")["cd_value"],
            created_at=facts["fc_created"],
            hls_formats=tuple(_parse_hls_formats(file["hls_resources"])),
            mp4_formats=tuple(_parse_mp4_formats(file["qualities"])),
        )


def _parse_hls_formats(sources: dict[str, str]) -> Generator[Format]:
    for name, uri in sources.items():
        if "multi" not in name:
            yield Format(
                codec="h264",
                quality=int(name.removeprefix("fl_cdn_")),
                url=_VIDEO_CDN / uri,
                average_bandwidth=0,
                hdr=False,
                size=0,
            )


def _parse_mp4_formats(qualities: dict[str, list[dict[str, Any]]]) -> Generator[Format]:
    for sources in qualities.values():
        for source in sources:
            yield Format.from_dict(source, url=_VIDEO_CDN / source["url"])
