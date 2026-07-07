from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, dates, parse_url
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    import datetime

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    DATE = "div.videobox span.stat:-soup-contains('Uploaded')"
    TITLE = "div.videobox > div.heading > h1"
    NEXT_PAGE = "a.next_page"
    VIDEO_THUMBS = "div.tile > a.thumb"

    _VIDEO = "div.videoplayer source"
    _IMAGE = "div.image_viewer img"
    MEDIA = f"{_IMAGE}, {_VIDEO}"


class EfuktCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/...",
        "Photo": "/pics/....",
        "Gif": "/view.gif.php?id=<id>",
        "Series": "/series/<series_name>",
        "Homepage": "/",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://efukt.com")
    DOMAIN: ClassVar[str] = "efukt.com"
    FOLDER_DOMAIN: ClassVar[str] = "eFukt"
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    ALLOW_EMPTY_PATH: ClassVar[bool] = True
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date:%Y-%m-%d} {title}"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["pics", _]:
                return await self.media(scrape_item)
            case ["view.gif.php"] if scrape_item.url.query.get("id"):
                return await self.media(scrape_item)
            case ["series", _]:
                return await self.series(scrape_item)
            case [slug]:
                if slug.isdigit():
                    return await self.homepage(scrape_item)
                if slug.endswith(".html"):
                    return await self.media(scrape_item)
                raise ValueError
            case []:
                return await self.homepage(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def homepage(self, scrape_item: ScrapeItem) -> None:
        async for soup in self.web_pager(scrape_item.url):
            for new_scrape_item in self.iter_children(scrape_item, soup, Selector.VIDEO_THUMBS):
                self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def series(self, scrape_item: ScrapeItem) -> None:
        soup, pages = await aio.peek_first(self.web_pager(scrape_item.url))
        title = css.select_text(soup, Selector.TITLE)
        scrape_item.setup_as_album(self.create_title(f"{title} [series]"))

        async for soup in pages:
            for new_scrape_item in self.iter_children(scrape_item, soup, Selector.VIDEO_THUMBS):
                self.create_task(self.run(new_scrape_item))

    @error_handling_wrapper
    async def media(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        media = await self._request_media(scrape_item.url)
        scrape_item.upload_date = media.date
        _, ext = self.get_filename_and_ext(media.src.name)
        title = f"{media.date.date().isoformat()} {media.title}"
        filename = self.create_custom_filename(title, ext, file_id=media.id)
        # Video links expire, but the path is always the same, only query params change
        await self.handle_file(media.src, scrape_item, title, ext, custom_filename=filename)

    async def _request_media(self, url: AbsoluteHttpURL) -> Media:
        soup = await self.request_soup(url)
        media = _parse_media(soup)
        media.id = url.query.get("id") or url.name.partition("_")[0]
        return media


@dataclasses.dataclass(slots=True)
class Media:
    date: datetime.datetime
    title: str
    src: AbsoluteHttpURL
    id: str = ""


def _parse_media(soup: BeautifulSoup) -> Media:
    date_str = css.select_text(soup, Selector.DATE).split(" ", 1)[-1]
    return Media(
        date=dates.parse_format(date_str, "%m/%d/%y"),
        src=parse_url(css.select(soup, Selector.MEDIA, "src")),
        title=css.select_text(soup, Selector.TITLE),
    )
