from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import Tag

    from cyberdrop_dl.url_objects import ScrapeItem


class ImageVenueCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Image": (
            "/<image_id>",
            "/view/o?i=<image_id>",
            "/img.php?image=<image_id>",
        ),
        "Thumbnail": "cdn-thumbs.imagevenue.com/.../<image_id>_t.jpg",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.imagevenue.com")
    DOMAIN: ClassVar[str] = "imagevenue"
    FOLDER_DOMAIN: ClassVar[str] = "ImageVenue"

    async def __async_post_init__(self) -> None:
        self.update_cookies({"nsfw_inter": 1, "continue": 1, "gdrp_popup_showed": 1})

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        if url.host.startswith("cdn-thumbs.") and url.name.endswith(suffix := "_t.jpg"):
            return cls.PRIMARY_URL / url.name.removesuffix(suffix)
        return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["img.php"] if scrape_item.url.query.get("image"):
                return await self.follow_redirect(scrape_item)
            case [image_id] if image_id.startswith("ME"):
                return await self.image(scrape_item)
            case ["view", "o"] if scrape_item.url.query.get("i") and scrape_item.url.query.get("h"):
                return await self.image(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        img = await self._request_img(scrape_item.url)
        src = self.parse_url(css.attr(img, "src"))
        name = css.attr(img, "alt")
        filename, ext = self.get_filename_and_ext(name, assume_ext=".jpg")
        await self.handle_file(src, scrape_item, name, ext, custom_filename=filename)

    async def _request_img(self, url: AbsoluteHttpURL) -> Tag:
        soup = await self.request_soup(url)
        try:
            return css.select(soup, "#main-image")
        except css.SelectorError:
            if redirect := soup.select_one("a[data-target-url][title='Continue to ImageVenue']"):
                url = self.parse_url(css.attr(redirect, "href"))
                soup = await self.request_soup(url)
                return css.select(soup, "#main-image")
            raise
