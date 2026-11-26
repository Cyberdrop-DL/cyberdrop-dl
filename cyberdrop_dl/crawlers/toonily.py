from __future__ import annotations

from typing import ClassVar, final

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem, ScrapeItemType
from cyberdrop_dl.utils import css, json_ld
from cyberdrop_dl.utils.dataclass import struct
from cyberdrop_dl.utils.errors import error_handling_wrapper


@final
class Selector:
    CHAPTER = ".wp-manga-chapter a"
    IMAGE = ".reading-content .page-break.no-gaps img"
    SERIES_TITLE = ".post-title > h1"
    NAV_BREADCUMBS = ".wp-manga-nav .breadcrumb li"


class ToonilyCrawler(Crawler):
    # TODO: Make this a general crawler for any site that uses wordpress madara
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Series": "/serie/<name>",
        "Chapter": "/serie/<name>/chapter-<chapter-id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://toonily.com")
    DOMAIN: ClassVar[str] = "toonily"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["serie", _]:
                await self.series(scrape_item)
            case ["serie", _, chapter] if chapter.startswith("chapter-"):
                await self.chapter(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def series(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url, impersonate=True)
        title = await css.aselect_text(soup, Selector.SERIES_TITLE, decompose="*")
        scrape_item.setup_as_profile(self.create_title(title))

        sleep = aio.periodic_sleep(10)
        for new_item in self.iter_children(scrape_item, soup, Selector.CHAPTER):
            self.create_task(self.run(new_item))
            await sleep()

    @error_handling_wrapper
    async def chapter(self, scrape_item: ScrapeItem) -> None:
        html = await self.request_html(scrape_item.url, impersonate=True)
        chapter = await _extr_chapter(html)

        if scrape_item.type != ScrapeItemType.PROFILE:
            series_title = self.create_title(chapter.series)
            scrape_item.append_folders(series_title)

        scrape_item.setup_as_album(chapter.title)
        scrape_item.uploaded_at = chapter.uploaded_at

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            for image in chapter.images:
                tg.create_task(self.direct_file(scrape_item, image))
                scrape_item.add_children()
                await sleep()


@struct
class Chapter:
    title: str
    series: str
    uploaded_at: float
    images: tuple[AbsoluteHttpURL, ...]


@aio.to_thread
def _extr_chapter(html: str) -> Chapter:
    soup = css.soup(html)

    *_, series_name, chapter_title = (css.text(bc) for bc in soup.select(Selector.NAV_BREADCUMBS))

    return Chapter(
        title=chapter_title,
        series=series_name,
        uploaded_at=json_ld.date_published(soup),
        images=tuple(ToonilyCrawler.iter_urls(soup, Selector.IMAGE, "src")),
    )
