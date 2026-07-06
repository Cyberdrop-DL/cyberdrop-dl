"""XFileSharing, XFileSharingPro and XVideoSharing.

https://sibsoft.net/xfilesharing.html"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import extr_text, parse_url
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem


class XFSCrawler(Crawler, is_abc=True):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "File": (
            "/e/<file_id>",
            "/d/<file_id>",
            "/file/<file_id>",
            "/embed/<file_id>",
            "/embed-<file_id>.html",
        )
    }
    NEEDS_REFERER: ClassVar[bool] = False

    @staticmethod
    def _raise_needs_referer():
        raise ScrapeError(403, "Referer required to download this video")

    @classmethod
    def extract_file_id(cls, url: AbsoluteHttpURL) -> str | None:
        match url.parts[1:]:
            case ["embed" | "e" | "d" | "file", file_id]:
                return file_id
            case [slug] if slug.startswith(a := "embed-") and slug.endswith(b := ".html"):
                return slug[len(a) : -len(b)] or None
            case _:
                return None


class XVideoSharingCrawler(XFSCrawler, is_abc=True):
    @classmethod
    def extract_stream(cls, html: str) -> AbsoluteHttpURL:
        start = html.index("sources:", html.index('jwplayer("vplayer").setup'))
        url = extr_text(html[start:], "file:", "}]")
        return parse_url(url.strip('"'))

    @error_handling_wrapper
    async def embed(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        referer = scrape_item.referer or (scrape_item.parents[-1] if scrape_item.parents else None)
        m3u8_url = await self.request_stream(video_id, referer)
        m3u8, info = await self.request_m3u8_playlist(m3u8_url)
        filename = self.create_custom_filename(
            video_id,
            ext := ".mp4",
            resolution=info.resolution,
            video_codec=info.codecs.video,
        )
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            filename,
            ext,
            m3u8=m3u8,
            referer=referer,
        )

    async def request_stream(self, video_id: str, referer: AbsoluteHttpURL | None = None) -> AbsoluteHttpURL:
        if self.NEEDS_REFERER and not referer:
            self._raise_needs_referer()

        return await self._stream_from_embed(video_id, referer or self.PRIMARY_URL)

    async def _stream_from_embed(self, video_id: str, referer: AbsoluteHttpURL) -> AbsoluteHttpURL:
        iframe_url = self.PRIMARY_URL / f"embed-{video_id}.html"
        html = await self.request_text(iframe_url, headers={"Referer": str(referer)})

        if (msg := "Video embed restricted for this domain") in html:
            if referer == self.PRIMARY_URL:
                self._raise_needs_referer()
            raise ScrapeError(403, msg)

        if "File is no longer available" in html:
            raise ScrapeError(404)

        return self.extract_stream(html)


if TYPE_CHECKING:
    _XVSMixinBase = XVideoSharingCrawler

else:
    _XVSMixinBase = object


class EmbedOnlyMixin(_XVSMixinBase):
    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        if video_id := cls.extract_file_id(url):
            return url.origin() / "embed" / video_id
        return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["embed", video_id]:
                return await self.embed(scrape_item, video_id)
            case _:
                raise ValueError
