from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers._kvs import KernelVideoSharingCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import open_graph
from cyberdrop_dl.utils.errors import error_handling_wrapper


class YourLesbiansCrawler(KernelVideoSharingCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://yourlesbians.com")
    DOMAIN: ClassVar[str] = "yourlesbians.com"
    FOLDER_DOMAIN: ClassVar[str] = "YourLesbians"
    DEFAULT_TRIM_URLS: ClassVar[bool] = False

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str | None = None) -> None:
        soup = await self.request_soup(scrape_item.url)
        name = open_graph.title(soup)
        title = self.create_title(f"{name} [album]", album_id)
        scrape_item.setup_as_album(title, album_id=album_id)
        for img in self.iter_urls(soup, ".album-inner a.album-img"):
            self.create_eager_task(self.direct_file(scrape_item, img))
            scrape_item.add_children()
