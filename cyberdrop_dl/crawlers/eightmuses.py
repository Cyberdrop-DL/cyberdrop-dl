from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    TILE = "a[class*=c-tile]"
    IMAGE = "div[class=image]"
    TITLE_PARTS = "div[class=top-menu-breadcrumb] > ol > li > a"


class EightMusesCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Album": "/comics/album/..."}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://comics.8muses.com")
    DOMAIN: ClassVar[str] = "8muses"
    FOLDER_DOMAIN: ClassVar[str] = "8Muses"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if "album" in scrape_item.url.parts:
            return await self.album(scrape_item)
        raise ValueError

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)

        album_id = scrape_item.album_id
        if not album_id:
            title_parts = get_title_parts(soup)
            album_title = title_parts[-1]
            album_id = album_title.replace(" ", "-")
            title = self.create_title(album_title, scrape_item.album_id)
            scrape_item.setup_as_album(title, album_id=album_id)

        results = await self.get_album_results(album_id)

        for tile in soup.select(Selector.TILE):
            tile_link = self.parse_url(css.attr(tile, "href"))
            tile_title: str = css.attr_or_none(tile, "title") or ""
            image = css.select(tile, Selector.IMAGE)
            is_new_album = image["itemtype"] == "https://schema.org/ImageGallery"
            new_album_id = f"{scrape_item.album_id}/{tile_title.replace(' ', '-')}"
            new_scrape_item = scrape_item.create_child(tile_link)
            new_scrape_item.append_folders(tile_title)
            new_scrape_item.album_id = new_album_id
            if is_new_album:
                await self.album(new_scrape_item)
                continue

            image_link_str: str = css.select(image, "img", "data-src").replace("/th/", "/fm/")
            image_link = self.parse_url(image_link_str)
            if not self.check_album_results(image_link, results):
                filename, ext = self.get_filename_and_ext(f"{tile_title}.jpg")
                await self.handle_file(image_link, new_scrape_item, filename, ext)
            scrape_item.add_children()


def get_title_parts(soup: BeautifulSoup) -> list[str]:
    """Gets the album title, sub-album title, and comic title."""
    titles = soup.select(Selector.TITLE_PARTS)[1:]
    return [title.get_text() for title in titles]
