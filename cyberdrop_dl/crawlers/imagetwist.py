from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths, URLConfig
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


@URLConfig(strict_host_match=True)
class ImageTwistCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = (
        "croea.com",
        "imagehaha.com",
        "imagenimage.com",
        "imagenpic.com",
        "imageshimage.com",
        "imagexport.com",
        "picshick.com",
        "picturelol.com",
    )
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Image": (
            "/<id>",
            "/<id>/<name>",
            "/t/<n>/<id>/<name>",
            "/i/<n>/<id>/<name>",
        )
    }
    DOMAIN: ClassVar[str] = "imagetwist"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://imagetwist.com")

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["th" | "i", _, image_id, *_]:
                return cls.PRIMARY_URL / image_id
            case [image_id, _]:
                return cls.PRIMARY_URL / image_id
            case _:
                return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [slug] if (image_id := Path(slug).stem) and len(image_id) == 12:
                await self.image(scrape_item, image_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem, image_id: str) -> None:
        referer = self.PRIMARY_URL / image_id
        if await self.check_complete_from_referer(referer):
            return

        soup = await self.request_soup(scrape_item.url)
        scrape_item.url = referer
        src = self.parse_url(css.select(soup, ".it-image-zoom-link img", "src"))
        await self.direct_file(scrape_item, src)
