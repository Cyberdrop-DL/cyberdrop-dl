from __future__ import annotations

from http import HTTPStatus
from typing import ClassVar, final, override

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.network import etag
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper


@final
class Selector:
    IMAGE = "#img"
    IMAGES = "#gallery-view-content img"
    ALBUM_TITLE = "div#gallery-view h1"
    NOT_FOUND = "h2:-soup-contains-own('The specified gallery could not be found')"
    UNAVAILABLE = ".notice:-soup-contains('In the meantime, please visit our sponsor')"


etag.register(etag.ETag("6a748841-1f9b", "Image temporarily unavailable", HTTPStatus.SERVICE_UNAVAILABLE))


class ImgBoxCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/g/<gallery_id>",
        "Image": (
            "/<img_id>",
            "thumbs.imgbox.com/../../<img_id>.<ext>",
            "images.imgbox.com/../../<img_id>.<ext>",
        ),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://imgbox.com")
    DOMAIN: ClassVar[str] = "imgbox"
    FOLDER_DOMAIN: ClassVar[str] = "ImgBox"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["g", gallery_id]:
                await self.album(scrape_item, gallery_id)
            case [_]:
                await self.image(scrape_item)
            case _:
                raise ValueError

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        if cls.is_subdomain(url) or "_" in url.name:
            return cls.PRIMARY_URL / url.name.partition("_")[0].partition(".")[0]
        return url

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        if soup.select_one(Selector.NOT_FOUND):
            raise ScrapeError(404)

        name = css.select_text(soup, Selector.ALBUM_TITLE).rsplit(" - ", 1)[0]
        scrape_item.setup_as_album(self.create_title(name, album_id), album_id=album_id)

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            for src in map(_thumb_to_src, self.iter_urls(soup, Selector.IMAGES, "src")):
                tg.create_task(self.direct_file(scrape_item, src))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        if soup.select_one(Selector.UNAVAILABLE):
            raise ScrapeError(HTTPStatus.SERVICE_UNAVAILABLE)

        src = _thumb_to_src(self.parse_url(css.select(soup, Selector.IMAGE, "src")))
        await self.direct_file(scrape_item, src)


def _thumb_to_src(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    return url.with_host(url.host.replace("thumbs", "images")).with_name(url.name.replace("_b", "_o"))
