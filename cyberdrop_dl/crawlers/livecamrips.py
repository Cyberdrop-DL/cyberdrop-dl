from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import Crawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedPaths
    from cyberdrop_dl.url_objects import ScrapeItem


@HTTPConfig(rate_limit=(4, 1))
class LiveCamRipsCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/video/<video_id>",
        "Model": "/model/<model_id>",
    }
    NEXT_PAGE_SELECTOR: ClassVar[str] = "a.tm-btn-next[href^=http]:-soup-contains-own('Next Page')"
    DOMAIN: ClassVar[str] = "livecamrips"
    FOLDER_DOMAIN: ClassVar[str] = "LiveCamRips"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://livecamrips.to")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video", _]:
                await self.video(scrape_item)
            case ["model", _, *_]:
                await self.model(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return
        soup = await self.request_soup(scrape_item.url)

        title = css.select(soup, "h1")
        user_name = css.select_text(title, "a")
        css.decompose(title, "a")

        _, site_name, upload_date = map(str.strip, css.text(title).rsplit("- ", 2))
        scrape_item.setup_as_profile(self.create_title(f"{user_name} [{site_name}]"))
        scrape_item.uploaded_at = self.parse_iso_date(upload_date)
        scrape_item.append_folders(f"Show on {upload_date}")
        embed_url = self.parse_url(css.select(soup, "#iframe-video", "src"))
        new_item = scrape_item.create_child(embed_url)
        new_item.referer = scrape_item.referer
        self.handle_embed(new_item)

    @error_handling_wrapper
    async def model(self, scrape_item: ScrapeItem) -> None:
        scrape_item.setup_as_profile("")
        async for soup in self.web_pager(scrape_item.url):
            for new_item in self.iter_children(scrape_item, soup, ".tm-video-item > a"):
                self.create_task(self.run(new_item))
