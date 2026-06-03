from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    GALLERY_TITLE = "a.link h2"
    GALLERY_IMAGES = "div.images a"
    IMAGE = "img.image-img"


PRIMARY_URL = AbsoluteHttpURL("https://pixhost.to")


class PixHostCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Gallery": "/gallery/<gallery_id>",
        "Image": "/show/<image_id>",
        "Thumbnail": "/thumbs/..",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    UPDATE_UNSUPPORTED: ClassVar[bool] = True
    DOMAIN: ClassVar[str] = "pixhost"
    FOLDER_DOMAIN: ClassVar[str] = "PixHost"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("pixhost.org",)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["thumbs", _, *_] if self.is_subdomain(scrape_item.url):
                src = _thumbnail_to_src(scrape_item.url)
                scrape_item.url = _thumbnail_to_web_url(scrape_item.url)
                return await self.direct_file(scrape_item, src)
            case ["gallery", gallery_id]:
                return await self.gallery(scrape_item, gallery_id)
            case ["show", _, *_]:
                return await self.image(scrape_item)
            case ["images", _, *_]:
                return await self.direct_file(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def gallery(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        title = css.select_text(soup, Selector.GALLERY_TITLE)
        title = self.create_title(title, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)
        results = await self.get_album_results(album_id)

        for thumb, web_url in self.iter_tags(soup, Selector.GALLERY_IMAGES):
            assert thumb
            src = _thumbnail_to_src(thumb)
            if self.check_album_results(src, results):
                continue
            new_scrape_item = scrape_item.create_child(web_url)
            self.create_task(self.direct_file(new_scrape_item, src))
            scrape_item.add_children()

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        link_str = css.select(soup, Selector.IMAGE, "src")
        link = self.parse_url(link_str)
        await self.direct_file(scrape_item, link)


def _thumbnail_to_src(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    # https://t100.pixhost.to/thumbs/491/538303440_005.jpg -> https://img100.pixhost.to/images/491/538303440_005.jpg
    thumb_server_id = url.host.split(".", 1)[0].split("t")[-1]
    img_host = f"img{thumb_server_id}.{PRIMARY_URL.host}"
    new_path = url.path.replace("/thumbs/", "/images/")
    return url.with_host(img_host).with_path(new_path)


def _thumbnail_to_web_url(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    new_path = url.path.replace("/thumbs/", "/show/")
    return url.with_host(PRIMARY_URL.host).with_path(new_path)
