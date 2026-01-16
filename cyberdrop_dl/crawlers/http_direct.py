from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.constants import FILE_FORMATS
from cyberdrop_dl.crawlers.crawler import Crawler
from cyberdrop_dl.exceptions import NoExtensionError
from cyberdrop_dl.utils.utilities import get_filename_and_ext

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


MEDIA_EXTENSIONS = FILE_FORMATS["Images"] | FILE_FORMATS["Videos"] | FILE_FORMATS["Audio"]


class DirectHttpFile(Crawler, is_generic=True):
    DOMAIN: ClassVar[str] = "no_crawler"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        try:
            filename, ext = get_filename_and_ext(scrape_item.url.name)
        except NoExtensionError:
            filename, ext = get_filename_and_ext(scrape_item.url.name, forum=True)

        if ext not in MEDIA_EXTENSIONS:
            raise ValueError

        scrape_item.add_to_parent_title("Loose Files")
        scrape_item.part_of_album = True
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            scrape_item.url.name,
            ext,
            custom_filename=filename,
        )
