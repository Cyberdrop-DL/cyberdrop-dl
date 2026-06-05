from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem
from cyberdrop_dl.utils import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.url_objects import ScrapeItem
    from cyberdrop_dl.utils import m3u8


_CDN_HOST = "pbs.twimg.com"


class TwimgCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Photo": "/..."}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://twimg.com/")
    DOMAIN: ClassVar[str] = "twimg"
    FOLDER_DOMAIN: ClassVar[str] = "TwitterImages"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if "video" in scrape_item.url.host:
            return await self.direct_file(scrape_item)
        await self.photo(scrape_item)

    @error_handling_wrapper
    async def photo(self, scrape_item: ScrapeItem, url: AbsoluteHttpURL | None = None) -> None:
        # https://developer.x.com/en/docs/x-api/v1/data-dictionary/object-model/entities#photo_format
        link = url or scrape_item.url
        if "emoji" in link.parts:
            return

        # name could be "orig", "4096x4096", "large", "medium", or "small"
        # `orig`` is original quality but it's not always available, same as "4096x4096"
        # "large", "medium", or "small" are always available

        link = next(_make_download_urls(link.with_host(_CDN_HOST)))
        filename = Path(link.name).with_suffix(".jpg").as_posix()
        filename, ext = self.get_filename_and_ext(filename)
        await self.handle_file(link, scrape_item, filename, ext)

    async def handle_media_item(self, media_item: MediaItem, m3u8: m3u8.Rendition | None = None) -> None:
        if media_item.referer == media_item.url and media_item.parents:
            media_item.referer = media_item.parents[0]
        await super().handle_media_item(media_item, m3u8)


def _make_download_urls(base_url: AbsoluteHttpURL) -> Generator[AbsoluteHttpURL]:
    for name in ("orig", "4096x4096", "large"):
        yield base_url.with_query(format="jpg", name=name)
