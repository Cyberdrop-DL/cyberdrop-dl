from __future__ import annotations

import dataclasses
import json
import logging
from typing import TYPE_CHECKING, Any, ClassVar, Unpack, override

from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import API, Crawler, DownloadConfig, SupportedDomains, SupportedPaths, URLConfig
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.crypto import aes_cbc_decrypt
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.clients import HttpMethod
    from cyberdrop_dl.clients.request import RequestParams
    from cyberdrop_dl.url_objects import ScrapeItem

logger = logging.getLogger(__name__)


@Crawler.db_path_builder("path_qs_frag")
@URLConfig(allow_empty_path=True, ignore_fragment=False, trim=False)
@HTTPConfig(headers={"Origin": "https://videosh.upns.live", "Referer": "https://videosh.upns.live/"})
@DownloadConfig(slots=2, ignore_content_type=True)
class VidStackCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = ("videosh.upns.live", "vidstack.io")
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Video": "/#<video_id>"}
    DOMAIN: ClassVar[str] = "vidstack"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://videosh.upns.live")

    def __post_init__(self) -> None:
        self.api: VidStackAPI = VidStackAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if video_id := scrape_item.url.fragment:
            return await self.video(scrape_item, video_id)
        raise ValueError

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        if url.fragment:
            return url.with_fragment(url.fragment.partition("/")[0].partition("&")[0])
        return url

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        video = await self.api.video(video_id, scrape_item.referer)
        m3u8, info = await self.request_m3u8_playlist(video.src)
        custom_filename = self.create_custom_filename(
            video.title,
            ext := ".mp4",
            file_id=video_id,
            resolution=info.resolution,
        )

        await self.handle_file(
            scrape_item.url,
            scrape_item,
            video.title,
            ext,
            m3u8=m3u8,
            custom_filename=custom_filename,
            thumbnail=video.thumb,
        )


@dataclasses.dataclass(slots=True, frozen=True)
class Video:
    id: str
    title: str
    thumb: AbsoluteHttpURL
    src: AbsoluteHttpURL


class VidStackAPI(API):
    KEY: ClassVar[bytes] = b"kiemtienmua911ca"
    IVS: ClassVar[tuple[bytes, ...]] = (b"1234567890oiuytr", b"0123456789abcdef")

    async def video(self, video_id: str, referer: AbsoluteHttpURL | None = None) -> Video:
        url = (self.origin / "api/v1/video").with_query(id=video_id)
        info = await self.request_aes_json(url, referer=referer)
        return Video(
            video_id,
            info["title"],
            thumb=self.parse_url(info["poster"], self.origin),
            src=self.parse_url(info["source"], self.origin),
        )

    async def request_aes(
        self,
        url: AbsoluteHttpURL,
        method: HttpMethod = "GET",
        referer: AbsoluteHttpURL | None = None,
        **kwargs: Unpack[RequestParams],
    ) -> str:
        if referer:
            url = url.update_query(r=str(referer))
            headers = kwargs.setdefault("headers", {})
            headers["Referer"] = str(referer)
            headers["Origin"] = str(referer.origin())

        text = await self.request_text(url, method, **kwargs)
        content = bytes.fromhex(text.strip())

        for iv in self.IVS:
            try:
                return aes_cbc_decrypt(content, self.KEY, iv).decode("utf8")
            except Exception:
                logger.exception("")
                continue

        raise ScrapeError(422, "Unable to decode encrypted response")

    async def request_aes_json(
        self,
        url: AbsoluteHttpURL,
        method: HttpMethod = "GET",
        referer: AbsoluteHttpURL | None = None,
        **kwargs: Unpack[RequestParams],
    ) -> dict[str, Any]:
        content = (await self.request_aes(url, method, referer, **kwargs)).strip()
        try:
            return json.loads(content)
        except ValueError:
            return json.loads(content[: content.rindex("}") + 1])
