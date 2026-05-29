from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper, extr_text, open_graph

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedPaths
    from cyberdrop_dl.url_objects import ScrapeItem


class Selector:
    VIDEO = "input[name=fid]"
    USER_NAME = "div.info a[href*='archivebate.store/profile/']"
    SITE_NAME = f"{USER_NAME} + p"


class ArchiveBateCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/watch/<video_id>",
    }
    DOMAIN: ClassVar[str] = "archivebate"
    FOLDER_DOMAIN: ClassVar[str] = "ArchiveBate"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.archivebate.store")
    _RATE_LIMIT: ClassVar[RateLimit] = 4, 1

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["watch", _]:
                return await self.video(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)

        if "This video has been deleted" in soup.get_text():
            raise ScrapeError(410)

        upload_date = extr_text(open_graph.description(soup), "show on", " - ").strip()
        user_name = css.select_text(soup, Selector.USER_NAME)
        site_name = css.select_text(soup, Selector.SITE_NAME)
        scrape_item.setup_as_profile(self.create_title(f"{user_name} [{site_name}]"))

        scrape_item.uploaded_at = self.parse_iso_date(upload_date)
        scrape_item.append_folder(f"Show on {upload_date}")
        embed_url = self.parse_url(css.select(soup, Selector.VIDEO, "value"))
        self.handle_embed(scrape_item.create_child(embed_url))
