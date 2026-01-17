from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


class PostImgCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/gallery/<album_id>/...",
        "Image": "/<image_id>/...",
        "Direct links": "i.postimg.cc/<image_id>/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://postimg.cc")
    DOMAIN: ClassVar[str] = "postimg"
    FOLDER_DOMAIN: ClassVar[str] = "PostImg"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = "postimg.org", "postimages.org"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if "i.postimg.cc" in scrape_item.url.host:
            return await self.direct_file(scrape_item)

        match scrape_item.url.parts[1:]:
            case ["gallery", album_id, *_]:
                return await self.album(scrape_item, album_id)
            case _:
                await self.image(scrape_item)

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        title = self.create_title(scrape_item.url.name, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        for page in itertools.count(1):
            resp = await self.request_json(
                self.PRIMARY_URL / "json",
                method="POST",
                data={
                    "action": "list",
                    "album": album_id,
                    "page": page,
                },
            )

            for image in resp["images"]:
                link = self.PRIMARY_URL / image[0]
                self.create_task(self.run(scrape_item.create_child(link)))
                scrape_item.add_children()

            if not resp["has_page_next"]:
                break

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        soup = await self.request_soup(scrape_item.url)
        link_str = css.select(soup, "a#download", "href")
        link = self.parse_url(link_str).with_query(None)
        name = css.select_text(soup, ".mb-4 + h6")
        filename, ext = self.get_filename_and_ext(name + link.suffix)
        await self.handle_file(link, scrape_item, filename, ext)
