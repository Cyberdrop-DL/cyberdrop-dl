from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import extr_text, parse_url
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class ABStreamCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/e/<video_id>",
            "/embed/<video_id>",
            "/embed-<video_id>.html",
        )
    }

    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://abstream.to")
    DOMAIN: ClassVar[str] = "abstream"
    FOLDER_DOMAIN: ClassVar[str] = "ABStream"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["embed", video_id]:
                return await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["e", video_id]:
                return url.origin() / "embed" / video_id
            case [slug] if video_id := _video_id(slug):
                return url.origin() / "embed" / video_id
            case _:
                return url

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        referer = scrape_item.parents[-1] if scrape_item.parents else self.PRIMARY_URL
        m3u8_url = await self._request_stream(video_id, referer)
        m3u8, info = await self.request_m3u8_playlist(m3u8_url)
        filename = self.create_custom_filename(
            video_id, ext := ".mp4", resolution=info.resolution, video_codec=info.codecs.video
        )
        await self.handle_file(scrape_item.url, scrape_item, filename, ext, m3u8=m3u8, referer=referer)

    async def _request_stream(self, video_id: str, referer: AbsoluteHttpURL) -> AbsoluteHttpURL:
        iframe_url = self.PRIMARY_URL / f"embed-{video_id}.html"
        html = await self.request_text(iframe_url, headers={"Referer": str(referer)})
        if (msg := "Video embed restricted for this domain") in html:
            if referer == self.PRIMARY_URL:
                msg = "Referer required to download this video"
            raise ScrapeError(403, msg)
        if "File is no longer available" in html:
            raise ScrapeError(404)

        return _extract_stream(html)


def _extract_stream(html: str) -> AbsoluteHttpURL:
    start = html.index("sources:", html.index('jwplayer("vplayer").setup'))
    url = extr_text(html[start:], "file:", "}]")
    return parse_url(url.strip('"'))


def _video_id(slug: str) -> str | None:
    if slug.startswith(a := "embed-") and slug.endswith(b := ".html"):
        return slug[len(a) : -len(b)]
