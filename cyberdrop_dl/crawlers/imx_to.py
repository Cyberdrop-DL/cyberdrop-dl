from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class Selector:
    GALLERY_TITLE = "div.title"
    GALLERY_IMAGES = "div.tooltip a"
    IMAGES = "div#container a > img"


class ImxToCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Image": (
            "/i/...",
            "/u/i/...",
        ),
        "Thumbnail": (
            "/t/...",
            "/u/t/",
        ),
        "Gallery": "/g/<gallery_id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://imx.to")
    DOMAIN: ClassVar[str] = "imx.to"

    async def async_startup(self) -> None:
        self.update_cookies({"continue": 1})

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["g", gallery_id]:
                return await self.gallery(scrape_item, gallery_id)
            case ["i", _]:
                return await self.image(scrape_item)
            case _:
                raise ValueError

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        match url.parts[1:]:
            case ["u" | "i" | "t", _, _, *_]:
                return cls.PRIMARY_URL / "i" / Path(url.name).stem
            case _:
                return url

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(
            scrape_item.url,
            method="POST",
            data={"imgContinue": "Continue+to+image+...+"},
        )
        image = css.select_one(soup, Selector.IMAGES)
        name = css.get_attr(image, "alt")
        link = self.parse_url(css.get_attr(image, "src"))
        filename, ext = self.get_filename_and_ext(name)
        await self.handle_file(link, scrape_item, name, ext, custom_filename=filename)

    @error_handling_wrapper
    async def gallery(self, scrape_item: ScrapeItem, album_id: str) -> None:
        soup = await self.request_soup(scrape_item.url)
        name = css.select_one_get_text(soup, Selector.GALLERY_TITLE)
        title = self.create_title(name, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        results = await self.get_album_results(album_id)
        for _, new_scrape_item in self.iter_children(scrape_item, soup, Selector.GALLERY_IMAGES, results=results):
            self.create_task(self.run(new_scrape_item))
