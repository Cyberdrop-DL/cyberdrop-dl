from __future__ import annotations

import base64
import json
import re
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, dates
from cyberdrop_dl.utils.dataclass import struct
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Mapping

    from cyberdrop_dl.url_objects import ScrapeItem


class SxyPrnCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/post/<video_id>.html",
    }
    DOMAIN: ClassVar[str] = "sxyprn"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.sxyprn.com")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["post", slug]:
                video_id = slug.removesuffix(".html")
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        url = self.PRIMARY_URL / f"post/{video_id}.html"
        if await self.check_complete(url):
            return

        scrape_item.url = url
        video = await _parse_video(await self.request_html(url), video_id)
        scrape_item.uploaded_at = video.uploaded

        await self.handle_file(
            url,
            scrape_item,
            video.clean_name,
            ext := ".mp4",
            custom_filename=self.create_custom_filename(video.clean_name, ext, file_id=video_id),
            thumbnail=video.thumb,
            metadata=video,
            debrid_link=video.src,
        )


@struct
class Video:
    id: str
    uploaded: int
    name: str
    clean_name: str
    duration: str
    tags: tuple[str, ...]
    src: AbsoluteHttpURL
    thumb: AbsoluteHttpURL
    external: tuple[AbsoluteHttpURL, ...]
    info: Mapping[str, str]


@aio.to_thread
def _parse_video(html: str, video_id: str) -> Video:
    soup = css.soup(html)
    cdn = json.loads(css.select(soup, ".vidsnfo", "data-vnfo"))[video_id]
    post = css.select(soup, "div.post_el_wrap")

    del soup
    video, title = css.select(post, "#vid_container_id"), css.select(post, ".post_text h1")
    info = css.select_text(post, "div:-soup-contains-own('Video Info ->')")
    props = {css.attr(prop, "itemprop"): css.attr(prop, "content") for prop in css.iselect(video, "meta[itemprop]")}
    tags = tuple(css.iselect(title, "a.hash_link", "label"))

    return Video(
        id=video_id,
        name=props["name"],
        thumb=SxyPrnCrawler.parse_url(props["thumbnailUrl"]),
        duration=props["duration"],
        uploaded=dates.timestamp_from_iso(props["uploadDate"]),
        src=_decode_src(cdn),
        tags=tags,
        clean_name=_clean_name(props["name"], tags),
        external=tuple(map(SxyPrnCrawler.parse_url, css.iselect(title, "a.extlink", "href"))),
        info=dict(re.findall(r"(duration|resolution|bitrate|size):\s*(.*?)(?=\s*·|$)", info)),
    )


def _clean_name(name: str, tags: tuple[str, ...]) -> str:
    if not tags:
        return name
    trunc_name = name.rpartition(f"#{tags[-1]}")[0]
    for tag in tags:
        trunc_name = trunc_name.replace(f"#{tag}", "")
    return trunc_name.strip() or name


def _decode_src(cdn: str) -> AbsoluteHttpURL:
    def add(part: str) -> int:
        digits = [int(c) for c in part if c.isdigit()] or [0]
        return sum(digits)

    parts = cdn.split("/")
    prefix, suffix = add(parts[6]), add(parts[7])
    parts[1] = "cdn8"
    parts[5] = str(int(parts[5]) - prefix - suffix)
    parts.insert(2, base64.b64encode(f"{prefix}-sxyprn.com-{suffix}".encode()).decode())
    return SxyPrnCrawler.parse_url("/".join(parts))
