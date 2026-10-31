from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers._kvs import KernelVideoSharingCrawler, KVSAjaxPagination
from cyberdrop_dl.crawlers.crawler import SupportedPaths, URLConfig
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text, open_graph
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


@URLConfig(trim=False)
class PPPCrawler(KernelVideoSharingCrawler, ensure_trailing_slash=True):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/v/<video_id>/",
        "Model": "/s/<id>/",
        "Search": "/search/<query>/",
    }
    DOMAIN: ClassVar[str] = "ppp.porn"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://ppp.porn")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["v", video_id, *_]:
                await self.video2(scrape_item, video_id)
            case ["categories" | "s" as kind, _, *_]:
                kind = "model" if kind == "s" else "category"
                await self.collection2(scrape_item, kind)
            case ["search" as kind, query, *_]:
                await self.collection2(scrape_item, kind, query)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video2(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        html = await self.request_text(scrape_item.url)
        video = await _parse_video(html, video_id)
        scrape_item.uploaded_at = self.parse_iso_date(video.uploaded)
        m3u8, _ = await self.request_m3u8(video.m3u8)
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            video.title,
            ext := ".mp4",
            m3u8=m3u8,
            custom_filename=self.create_custom_filename(video.title, ext, file_id=video_id),
            thumbnail=video.thumb,
            metadata=video,
        )

    @error_handling_wrapper
    async def collection2(self, scrape_item: ScrapeItem, kind: str, query: str | None = None) -> None:
        soup = await self.request_soup(scrape_item.url)
        title = self._clean_title(css.select_text(soup, "h1", decompose="span"))
        scrape_item.setup_as_album(self.create_title(f"{title} [{kind}]"))

        if kind == "search":
            block_id = "list_videos_videos_list_search_result"
            from_params = ("from_videos", "from_albums")
        else:
            block_id = "list_videos_common_videos_list"
            from_params = "from"

        ajax_url = KVSAjaxPagination(block_id=block_id, q=query)(scrape_item.url)
        sleep = aio.periodic_sleep(10)
        async for soup in self._ajax_pager(ajax_url, from_params=from_params):
            for new_item in self.iter_children(scrape_item, soup, ".card-video__img a"):
                self.create_task(self.run(new_item))
                await sleep()


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class Video:
    id: str
    title: str
    uploaded: str
    src: AbsoluteHttpURL
    m3u8: AbsoluteHttpURL
    thumb: AbsoluteHttpURL


@aio.to_thread
def _parse_video(html: str, video_id: str) -> Video:
    soup = css.soup(html)
    stream = extr_text(html, "var stream = ", ";").strip("'")
    content = css.select(soup, ".content-details")
    return Video(
        id=video_id,
        title=css.select_text(content, ".content-details__title"),
        uploaded=open_graph.video_release_date(soup),
        m3u8=PPPCrawler.parse_url(stream),
        thumb=PPPCrawler.parse_url(open_graph.image(soup)),
        src=PPPCrawler.parse_url(css.select(content, "a:-soup-contains('下載')", "href")),
    )
