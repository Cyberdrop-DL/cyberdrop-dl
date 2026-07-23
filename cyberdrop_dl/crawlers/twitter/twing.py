from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem
    from cyberdrop_dl.utils import m3u8


class TwimgCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Photo": "/media/<media_id>...",
        "Video": "/amplify_video/<media_id>...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://twimg.com/")
    DOMAIN: ClassVar[str] = "twimg"
    FOLDER_DOMAIN: ClassVar[str] = "TwitterImages"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if "amplify_video_thumb" in scrape_item.url.parts or scrape_item.url.suffix == ".m3u8":
            raise ValueError
        if "video" in scrape_item.url.host:
            return await self.direct_file(scrape_item)
        await self.photo(scrape_item)

    @error_handling_wrapper
    async def photo(self, scrape_item: ScrapeItem, url: AbsoluteHttpURL | None = None) -> None:
        # https://docs.x.com/x-api/enterprise-gnip-2.0/fundamentals/data-dictionary#photo-media-url-formatting
        src = url or scrape_item.url
        if "emoji" in src.parts:
            return

        src = src.with_host("pbs.twimg.com").with_query(format="jpg", name=self.config.crawlers.twitter.image_size)
        name = Path(src.name).with_suffix(".jpg").as_posix()
        filename, ext = self.get_filename_and_ext(name)
        await self.handle_file(src, scrape_item, name, ext, custom_filename=filename)

    async def handle_media_item(self, media_item: MediaItem, m3u8: m3u8.Rendition | None = None) -> None:
        if media_item.referer.path == media_item.url.path and media_item.parents:
            media_item.referer = media_item.parents[0]
            media_item.headers["Referer"] = str(media_item.referer)
        await super().handle_media_item(media_item, m3u8)
