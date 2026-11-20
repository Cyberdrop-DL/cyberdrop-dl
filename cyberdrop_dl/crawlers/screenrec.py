from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, dates, xml
from cyberdrop_dl.utils.dataclass import struct
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.urls import parse_http_url

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class ScreenRecCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Share (video/image)": "/share/<id>",
        "Direct images": "/images/...",
    }
    DOMAIN: ClassVar[str] = "screenrec"
    FOLDER_DOMAIN: ClassVar[str] = "ScreenRec"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://screenrec.com")
    VIDEO_CORE: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://service.webvideocore.net")

    @override
    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["share", share_id]:
                await self.share(scrape_item, share_id)
            case ["images", _, *_] if self.is_subdomain(scrape_item.url):
                await self.direct_file(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def share(self, scrape_item: ScrapeItem, share_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        html = await self.request_html(scrape_item.url)
        try:
            clip_id = _extract_clip_id(html)
        except ValueError:
            try:
                img_src, name = await _extract_img(html)
            except css.SelectorError:
                raise ScrapeError(422, "Unable to extract image or video") from None

            await self.direct_file(
                scrape_item,
                img_src,
                filename=self.create_custom_filename(
                    name,
                    self.get_filename_and_ext(img_src.name).suffix,
                    file_id=share_id,
                ),
            )
        else:
            video = await self._request_video(clip_id, share_id)
            await self._video(scrape_item, video)

    async def _video(self, scrape_item: ScrapeItem, video: Video) -> None:
        m3u8, info = await self.request_m3u8_playlist(video.m3u8)
        name = video.title or video.id
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            name,
            ext := ".mp4",
            m3u8=m3u8,
            custom_filename=self.create_custom_filename(name, ext, file_id=video.share_id, resolution=info.resolution),
            thumbnail=video.thumb,
            metadata=video,
        )

    async def _request_video(self, clip_id: str, share_id: str) -> Video:
        url = self.VIDEO_CORE.with_query(
            l="info",
            a="xmlClipPath",
            page_url=str(self.PRIMARY_URL / "share" / share_id),
            clip_id=clip_id,
            version=5,
            preview=0,
            timezone_offset=0,
            init="true",
        )
        xml = await self.request_text(url)
        return await _parse_video(xml, clip_id, share_id)


@struct
class Video:
    id: str
    share_id: str
    title: str | None
    description: str | None
    long_description: str | None
    created: int
    m3u8: AbsoluteHttpURL
    thumb: str | None


@aio.to_thread
def _extract_img(html: str) -> tuple[AbsoluteHttpURL, str]:
    img = css.select(css.soup(html), "section div.popup img.content")
    return parse_http_url(css.attr(img, "src")), css.attr(img, "alt")


def _extract_clip_id(html: str) -> str:
    for name in ("clip_id", "live_id"):
        pattern = f'{name}\\s*:\\s*\\"([0-9a-zA-Z]{{3,}})\\"'
        if m := re.search(pattern, html):
            return m[1]

    raise ValueError("Unable to extract clip_id")


@aio.to_thread
def _parse_video(content: str, clip_id: str, share_id: str) -> Video:
    xml_doc = xml.XML(content)
    m3u8_url = xml.select_text(xml_doc, "info/url")
    meta = {ele.tag.removeprefix("clip_"): xml.text(ele) for ele in xml.select(xml_doc, "info/meta")}

    return Video(
        id=clip_id,
        share_id=share_id,
        title=meta.get("title"),
        description=meta.get("descr"),
        long_description=meta.get("long_descr"),
        created=int(dates.parse_format(meta["date_created"], "%d %b %Y").timestamp()),
        m3u8=parse_http_url(m3u8_url),
        thumb=meta.get("image"),
    )
