from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, open_graph
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class FilmArchivCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": ("/de/filmarchiv-on/video/<video_id>",),
    }
    DOMAIN: ClassVar[str] = "filmarchiv"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.filmarchiv.at")
    CDN: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://cdn.filmarchiv.at")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["de", "filmarchiv-on", "video", video_id]:
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        try:
            cdn_path = _extr_cdn_path(self.parse_url(open_graph.image(soup)))
        except ValueError:
            raise ScrapeError(422, "Unable to extract m3u8 URL") from None
        else:
            m3u8_url = self.CDN / f"{cdn_path}_sv1/playlist.m3u8"
            thumb = self.CDN / cdn_path / "poster.jpg"

        meta: dict[str, Any] = {
            css.text(css.select(row, "strong").extract()).removesuffix(":"): css.text(row)
            for row in soup.select("div.ce-video_detail .space-y-2 div.leading-tight")
        }
        name = meta.get("Originaltitel") or css.select_text(soup, "title-div")
        m3u8, info = await self.request_m3u8_playlist(m3u8_url)
        meta["rendition"] = info
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            name,
            ext := ".mp4",
            m3u8=m3u8,
            custom_filename=self.create_custom_filename(name, ext, file_id=video_id, resolution=info.resolution),
            thumbnail=thumb,
            metadata=meta,
        )


def _extr_cdn_path(thumb: AbsoluteHttpURL) -> str:
    match thumb.parts[thumb.parts.index("videostatic") + 1 :]:
        case [a, b, _]:
            return f"{a}/{b}"
        case _:
            raise ValueError
