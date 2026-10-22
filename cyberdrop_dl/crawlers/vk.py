from __future__ import annotations

import dataclasses
import re
from typing import TYPE_CHECKING, Any, ClassVar, Unpack, override

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import DDOSGuardError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.clients.request import RequestParams
    from cyberdrop_dl.constants import HttpMethod
    from cyberdrop_dl.url_objects import ScrapeItem


class VKCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/clip<video_id>",
            "/video<video_id>",
        ),
    }
    DOMAIN: ClassVar[str] = "vk"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vkvideo.ru")
    FOLDER_DOMAIN: ClassVar[str] = "VK"

    @staticmethod
    @override
    def __db_path__(url: AbsoluteHttpURL, /) -> str:
        return url.with_query(sorted(url.query.items())).without_query_params("token").path_qs

    def __post_init__(self) -> None:
        self.api: VKAPI = VKAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [slug] if slug.startswith(("clip", "video")):
                video_id = slug.removeprefix("clip").removeprefix("video")
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        video = await self.api.video(video_id)
        best_fmt = max(video.formats, key=lambda f: f.score)
        scrape_item.uploaded_at = video.uploaded_at
        m3u8 = info = debrid_url = None
        if best_fmt.hls:
            m3u8, info = await self.request_m3u8(best_fmt.url)
        else:
            debrid_url = best_fmt.url

        await self.handle_file(
            scrape_item.url,
            scrape_item,
            video.title,
            ext := ".mp4",
            m3u8=m3u8,
            custom_filename=self.create_custom_filename(
                video.title,
                ext,
                file_id=video_id,
                resolution=info.resolution if info else best_fmt.height,
            ),
            thumbnail=video.thumb,
            debrid_link=debrid_url,
            metadata=video,
        )


@dataclasses.dataclass(slots=True, frozen=True)
class Video:
    title: str
    uploaded_at: int
    thumb: str | None
    embed_html: str
    formats: tuple[Format, ...]


class VKAPI(API):
    @override
    async def request_json(
        self, url: AbsoluteHttpURL, /, method: HttpMethod = "GET", **kwargs: Unpack[RequestParams]
    ) -> Any:
        async with self.request(url, method, **kwargs) as resp:
            if resp.url.name == "challenge.html":
                raise DDOSGuardError("JS challenge from VK")
            return await resp.json()

    async def video(self, video_id: str) -> Video:
        url = self.PRIMARY_URL / "al_video.php"
        resp = await self.request_json(
            url,
            data={
                "act": "show",
                "video": video_id,
                "al": 1,
            },
            impersonate=True,
            headers={
                "Referer": str(url),
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        code, payload = resp["payload"]
        match code:
            case "8":
                raise ScrapeError(403, payload[0].strip('"'))
            case "3":
                raise ScrapeError(401)
            case _:
                pass

        html, options = payload[1], payload[-1]
        params = options["player"]["params"][0]
        if params.get("live") == 2:
            raise ScrapeError(422, "Live streams are not supported")

        return Video(
            title=css.unescape(params.get("md_title") or options["mvData"]["title"]),
            thumb=params.get("jpg") or params.get("short_video_cover"),
            uploaded_at=params["date"],
            formats=tuple(_extract_formats(params)),
            embed_html=html,
        )


@dataclasses.dataclass(slots=True, frozen=True)
class Format:
    name: str
    url: AbsoluteHttpURL
    height: int | None = None
    hls: bool = False

    @property
    def score(self) -> tuple[bool, int]:
        return (not self.hls, self.height or 0)


def _extract_formats(data: dict[str, Any]) -> Generator[Format]:
    for name, value in data.items():
        if not value or type(value) is not str or not value.startswith(("//", "http")):
            continue

        url = VKCrawler.parse_url(value)

        if name.startswith("hls") and name != "hls_live_playback":
            yield Format(name=name, url=url, hls=True)
            continue

        if name in {"extra_data", "live_mp4", "postlive_mp4"}:
            yield Format(name=name, url=url)
            continue

        if m := re.search(r"^(?:url|cache)(\d+)", name):
            yield Format(name=name, url=url, height=int(m.group(1)))
