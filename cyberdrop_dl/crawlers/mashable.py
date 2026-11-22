from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.mediaprops import Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import extr_text
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


@Crawler.db_path_builder("url")
class MashableCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = ("mashable.com",)
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": ("/<kind>/<slug>",),
    }
    DOMAIN: ClassVar[str] = "mashable"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://mashable.com")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_, _]:
                await self.video(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        video = _extr_ex_video(await self.request_html(scrape_item.url))
        scrape_item.uploaded_at = self.parse_iso_date(video["created_at"])
        meta = video["mediaData"]
        src = self.parse_url(meta["originalVideoUrl"])
        await self.handle_file(
            src,
            scrape_item,
            video["title"],
            ext := ".mp4",
            custom_filename=self.create_custom_filename(
                video["title"],
                ext,
                file_id=video["slug"],
                resolution=Resolution(meta["width"], meta["height"]),
                fps=meta["fps"],
            ),
            thumbnail=video.get("thumbnail_url"),
            metadata=video,
        )


def _extr_ex_video(html: str) -> dict[str, Any]:
    try:
        push = extr_text(html, "window.videoEmbeds.push(", ");")
    except ValueError:
        raise ScrapeError(422, "This page has no videos") from None

    data = "{" + extr_text(push, "data: {", "}},").replace("'", r"\\'") + "}}"
    return json.loads(data)
