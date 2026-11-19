from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class PicStateCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Image": (
            "/view/full/<id>",
            "/thumbs/small/<id>/<name>",
            "/files/<id>/<name>",
        )
    }
    DOMAIN: ClassVar[str] = "picstate"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://picstate.com")

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["thumbs", _, image_id, name]:
                return cls.PRIMARY_URL / "files" / image_id / name
            case _:
                return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["view", "full", _image_id]:
                await self.image(scrape_item)
            case ["files", image_id, _, *_]:
                src = scrape_item.url
                scrape_item.url = self.PRIMARY_URL / "view/full" / image_id
                await self.direct_file(scrape_item, src)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        src = self.parse_url(css.select(soup, "#image_container img", "src"))
        await self.direct_file(scrape_item, src)
