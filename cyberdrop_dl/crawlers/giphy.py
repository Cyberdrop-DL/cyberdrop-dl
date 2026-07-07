from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class GiPhyCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Gif": "/gifs/<slug>-<gif-id>",
        "Direct Link": "https://media*.giphy.com/media/<gif_id>",
    }
    DOMAIN: ClassVar[str] = "giphy"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://giphy.com")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["gifs", slug]:
                gif_id = slug.rpartition("-")[-1]
                return await self.gif(scrape_item, gif_id)
            case _:
                raise ValueError

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["media", *_, gif_id, _] if cls.is_subdomain(url):
                return cls.PRIMARY_URL / "gifs" / gif_id
            case _:
                return url

    @error_handling_wrapper
    async def gif(self, scrape_item: ScrapeItem, gif_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        api_url = (self.PRIMARY_URL / "services/oembed").with_query(url=str(scrape_item.url))
        resp: dict[str, str] = await self.request_json(api_url)
        title = resp["title"].partition(f" by {resp['author_name']}")[0].removesuffix(" GIF")
        src = self.parse_url(resp["url"])
        filename = self.create_custom_filename(title, src.suffix, file_id=gif_id)
        await self.handle_file(src, scrape_item, resp["title"], src.suffix, custom_filename=filename)
