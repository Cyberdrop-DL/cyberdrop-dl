from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class VidaraCrawler(Crawler, db_path="path_qs_frag"):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = (
        "xca.cymru",
        "vidara.to",
        "vidara.so",
        "streamix.so",
        "streamix.so",
        "stmix.io",
    )
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Video": "/e/<video_id>"}
    DOMAIN: ClassVar[str] = "vidara"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vidara.to")

    _DOWNLOAD_SLOTS: ClassVar[int | None] = 2

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["e", video_id]:
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        m3u8_url, thumbnail = await self._request_stream(video_id)
        m3u8, info = await self.request_m3u8_playlist(m3u8_url)
        name, ext = self.get_filename_and_ext(video_id + ".mp4")
        custom_filename = self.create_custom_filename(name, ext, resolution=info.resolution)

        await self.handle_file(scrape_item.url, scrape_item, name, ext, m3u8=m3u8, custom_filename=custom_filename)

        thumb_name = f"{Path(custom_filename).stem}_thumb{thumbnail.suffix}"
        filename, _ = self.get_filename_and_ext(thumb_name)
        await self.handle_file(
            referer := scrape_item.url.with_fragment("thumbnail"),
            scrape_item,
            thumb_name,
            thumbnail.suffix,
            custom_filename=filename,
            debrid_link=thumbnail,
            referer=referer,
        )

    async def _request_stream(self, video_id: str) -> tuple[AbsoluteHttpURL, AbsoluteHttpURL]:
        resp = await self.request_json(
            self.PRIMARY_URL / "api/stream",
            method="POST",
            json={
                "device": "web",
                "filecode": video_id,
            },
        )
        return (
            self.parse_url(resp["streaming_url"]),
            self.parse_url(resp["thumbnail"]),
        )
