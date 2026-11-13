from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, final, override

from cyberdrop_dl.crawlers import Registry
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths, auto_task_id
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


@final
class Selector:
    GALLERY_TITLE = "a#gallery-name"
    THUMBNAILS = "ul.images a.thumbnail"
    IMAGE = "img.main-image"
    GALLERY_INFO = "div.view-navigation a:has(i.fas.fa-reply)"
    IS_GALLERY = ".card-header:-soup-contains('Share this gallery')"
    NEXT_PAGE = "a.page-link[rel=next]"
    UNAVAILABLE = ".notice :-soup-contains('In the meantime, please visit our sponsor')"


@Registry.database.fix_referer
class ImageBamCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Gallery": "/gallery/<id>",
        "Image": (
            "/image/<id>",
            "images<x>.imagebam.com/<id>",
        ),
        "Gallery or Image": "/view/<id>",
        "Thumbnails": "thumbs<x>.imagebam.com/<id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://imagebam.com")
    DOMAIN: ClassVar[str] = "imagebam"
    FOLDER_DOMAIN: ClassVar[str] = "ImageBam"
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("www.imagebam.com",)

    def __post_init__(self) -> None:
        # This skips the "Continue to image" pages.
        self.update_cookies(
            dict.fromkeys(
                (
                    "nsfw_inter",
                    "sfw_inter",
                    "__bamrxm1_p",
                    "_pre_js",
                ),
                1,
            )
        )

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["gallery", _]:
                await self.gallery(scrape_item)
            case ["image", _]:
                await self.image(scrape_item)
            case ["view", _]:
                await self.view(scrape_item)
            case _:
                raise ValueError

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        if cls.is_subdomain(url):
            return thumbnail_to_img(url)
        return url

    @error_handling_wrapper
    async def view(self, scrape_item: ScrapeItem) -> None:
        # view URLs can be either a gallery or a single image.
        soup = await self.request_soup(scrape_item.url)
        if soup.select_one(Selector.IS_GALLERY):
            await self.gallery(scrape_item, soup)
        else:
            await self.image(scrape_item, soup)

    @error_handling_wrapper
    async def gallery(self, scrape_item: ScrapeItem, soup: BeautifulSoup | None = None) -> None:
        if not soup:
            soup = await self.request_soup(scrape_item.url)

        gallery_name = css.select_text(soup, Selector.GALLERY_TITLE)
        gallery_id = scrape_item.url.name
        title = self.create_title(gallery_name, gallery_id)
        scrape_item.setup_as_album(title, album_id=gallery_id)

        while True:
            for new_scrape_item in self.iter_children(scrape_item, soup, Selector.THUMBNAILS):
                self.create_task(self._image_task(new_scrape_item))

            try:
                next_page = css.select(soup, Selector.NEXT_PAGE, "href")
            except css.SelectorError:
                break
            soup = await self.request_soup(self.parse_url(next_page))

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem, soup: BeautifulSoup | None = None) -> None:
        if not soup:
            if await self.check_complete_from_referer(scrape_item.url):
                return

            soup = await self.request_soup(scrape_item.url)

        try:
            image_tag = css.select(soup, Selector.IMAGE)
        except css.SelectorError:
            if soup.select_one(Selector.UNAVAILABLE):
                raise ScrapeError(503) from None
            raise

        if not scrape_item.album_id and (gallery_info := soup.select_one(Selector.GALLERY_INFO)):
            gallery_id = self.parse_url(css.attr(gallery_info, "href")).name
            scrape_item.album_id = gallery_id

        title = css.attr(image_tag, "alt")
        link = self.parse_url(css.attr(image_tag, "src"))
        custom_filename, ext = self.get_filename_and_ext(title)
        await self.handle_file(link, scrape_item, link.name, ext, custom_filename=custom_filename)

    _image_task = auto_task_id(image)


def thumbnail_to_img(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    stem = Path(url.name).stem
    image_id = stem.removesuffix("_t").removesuffix("_o")
    if image_id != stem:
        return ImageBamCrawler.PRIMARY_URL / "view" / image_id
    return ImageBamCrawler.PRIMARY_URL / "image" / image_id
