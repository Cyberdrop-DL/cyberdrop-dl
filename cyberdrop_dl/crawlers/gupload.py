from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Final

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.mediaprops import Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import extr_text, xor_decrypt
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


_KEY: Final = b"G7#kP!2qZxV9mRwL"


def _decode_config(config_text: str) -> dict[str, Any]:
    _, payload = config_text.split("~", 1)
    config_bytes = base64.b64decode(payload)
    return json.loads(xor_decrypt(config_bytes, _KEY))


class GUploadCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Video": ("/data/e/<video_id>",)}
    DOMAIN: ClassVar[str] = "gupload"
    FOLDER_DOMAIN: ClassVar[str] = "GUpload"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://gupload.xyz")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["data", "e", video_id]:
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        config = await self._request_video_config(scrape_item.url)
        m3u8_url = self.parse_url(config["videoUrl"])
        m3u8, _ = await self.request_m3u8(m3u8_url)

        filename, ext = self.get_filename_and_ext(video_id + ".mp4")
        custom_filename = self.create_custom_filename(video_id, ext, resolution=Resolution.parse(m3u8_url))
        await self.handle_file(m3u8_url, scrape_item, filename, ext, m3u8=m3u8, custom_filename=custom_filename)
        thumbnail = self.parse_url(config["posterUrl"])
        thumb_name, ext = self.get_filename_and_ext(f"{Path(custom_filename).stem}_thumb{thumbnail.suffix}")
        await self.handle_file(
            thumbnail,
            scrape_item,
            f"{video_id}_thumb{thumbnail.suffix}",
            ext,
            custom_filename=thumb_name,
            referer=scrape_item.url.with_fragment("thumbnail"),
        )

    async def _request_video_config(self, url: AbsoluteHttpURL) -> dict[str, Any]:
        html = await self.request_text(url, impersonate=True)
        config_text = extr_text(html, "var _cfg = ", "');").partition("('")[-1]
        return _decode_config(config_text)
