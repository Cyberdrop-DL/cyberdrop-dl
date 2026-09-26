from __future__ import annotations

import asyncio
import base64
import dataclasses
import itertools
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths, URLConfig
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterable

    import bs4

    from cyberdrop_dl.url_objects import ScrapeItem


@URLConfig(allow_empty_path=True)
class PornPicsCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Categories": "/<category>/",
        "Channels": "/channels/<name>",
        "Gallery": "/galleries/<name>-<gallery_id>",
        "Pornstars": "/pornstars/<name>",
        "Video preview": "/videos/<video_id>",
        "Tags": "/tags/<name>",
        "Search": "/?q=<query>",
        "Direct links": "",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pornpics.com")
    DOMAIN: ClassVar[str] = "pornpics"
    FOLDER_DOMAIN: ClassVar[str] = "PornPics"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["galleries", slug, *_]:
                gallery_id = slug.rpartition("-")[-1]
                await self.gallery(scrape_item, gallery_id)
            case ["tag" | "tags" | "category" as col, _, *_]:
                await self.collection(scrape_item, col)
            case ["search" | "channel" | "channels" | "pornstar" | "pornstars" as col, query, *_]:
                await self.collection(scrape_item, col, query)
            case ["videos", video_id]:
                await self.video_preview(scrape_item, video_id)
            case [_, _, *_, album_id, name] if name and self.is_subdomain(scrape_item.url):
                scrape_item.album_id = album_id
                await self.direct_file(scrape_item)
            case [] if query := scrape_item.url.query.get("q"):
                await self.collection(scrape_item, "search", query)
            case [_]:
                await self.collection(scrape_item, "category")
            case _:
                raise ValueError

    async def _collection_pager(self, url: AbsoluteHttpURL) -> AsyncGenerator[Iterable[tuple[str, AbsoluteHttpURL]]]:
        limit: int = 20  # This is hardcoded server side
        page_url = url.without_query_params("offset").update_query(limit=limit)

        # We intentionally skip the first result cause offset 0 return HTML instead of JSON
        init_offset = min(int(url.query.get("offset") or 1), 1)

        for offset in itertools.count(init_offset, limit):
            async with self.request(page_url.update_query(offset=offset)) as resp:
                resp = await resp.json(content_type=False)

            yield ((str(gallery["gid"]), self.parse_url(gallery["g_url"])) for gallery in resp)

            if len(resp) < limit:
                break

    @error_handling_wrapper
    async def collection(self, scrape_item: ScrapeItem, kind: str, query: str | None = None) -> None:
        soup = await self.request_soup(scrape_item.url.without_query_params("limit", "offset"))
        name = (
            css.select_text(soup, ".entity-card-title__name, .page-title-section h1")
            .removesuffix(" Nude Pics")
            .removesuffix(" Porn Pics")
            .strip()
        )
        scrape_item.setup_as_profile(self.create_title(f"{name} [{kind.removesuffix('s')}]"))
        search_url = (
            (self.PRIMARY_URL / "search/srch.php").with_query(q=query.replace("-", " ")) if query else scrape_item.url
        )

        async for galleries in self._collection_pager(search_url):
            async with self.new_task_group() as tg:
                for gallery_id, gallery_url in galleries:
                    if self.was_scrapped_before(gallery_url):
                        continue
                    new_item = scrape_item.create_child(gallery_url)
                    tg.create_task(self.gallery(new_item, gallery_id))
                    scrape_item.add_children()

    @error_handling_wrapper
    async def gallery(self, scrape_item: ScrapeItem, gallery_id: str) -> None:
        soup, completed = await aio.gather(self.request_soup(scrape_item.url), self.get_completed_by_album(gallery_id))
        name = css.select_text(soup, ".gallery-title h1")
        title = self.create_title(name, gallery_id)
        scrape_item.setup_as_album(title, album_id=gallery_id)

        async with self.new_task_group() as tg:
            for url in self.iter_urls(soup, "div#main a.rel-link"):
                if url in completed:
                    continue

                tg.create_task(self.direct_file(scrape_item, url))

    @error_handling_wrapper
    async def video_preview(self, scrape_item: ScrapeItem, video_id: str) -> None:
        async with self.request(scrape_item.url) as resp:
            soup = await resp.soup()
            html = await resp.text()

        video = await asyncio.to_thread(_extr_video, soup, html)
        _, ext = self.get_filename_and_ext(video.src.name)
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            video.name,
            ext,
            custom_filename=self.create_custom_filename(video.name, ext, file_id=video_id),
            thumbnail=video.thumb,
            debrid_link=video.src,
        )


@dataclasses.dataclass(slots=True, frozen=True)
class PreviewVideo:
    name: str
    src: AbsoluteHttpURL
    thumb: AbsoluteHttpURL
    uploaded: float


def _extr_video(soup: bs4.Tag, html: str) -> PreviewVideo:
    pp_link = extr_text(html, "var P_LINK =", ";").strip("'").removeprefix("dd/")
    return PreviewVideo(
        src=PornPicsCrawler.parse_url(base64.b64decode(pp_link.encode()).decode()),
        uploaded=Crawler.parse_iso_date(
            css.select_text(soup, ".gallery-info__item:-soup-contains('Added on:') .info-rate")
        ),
        name=css.select_text(soup, ".title-section h1"),
        thumb=PornPicsCrawler.parse_url(css.select(soup, "video[poster]", "poster")),
    )
