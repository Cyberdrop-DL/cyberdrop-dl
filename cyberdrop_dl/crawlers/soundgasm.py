from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper, extr_text

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem

_CDN = AbsoluteHttpURL("https://media.soundgasm.net")


class SoundGasmCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Audio": "/u/<user>/<slug>",
        "User": "/u/<user>",
    }
    DOMAIN: ClassVar[str] = "soundgasm"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://soundgasm.net")
    _RATE_LIMIT: ClassVar[RateLimit] = 5, 1

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["u", user, _]:
                return await self.audio(scrape_item, user)
            case ["u", user]:
                return await self.user(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def user(self, scrape_item: ScrapeItem) -> None:
        scrape_item.setup_as_profile("")
        soup = await self.request_soup(scrape_item.url)

        for _, new_item in self.iter_children(scrape_item, soup, ".sound-details a"):
            self.create_task(self.run(new_item))

    @error_handling_wrapper
    async def audio(self, scrape_item: ScrapeItem, user: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        scrape_item.setup_as_profile(self.create_title(user))
        title, src = await self._request_audio(scrape_item.url)
        _, ext = self.get_filename_and_ext(src.name)
        filename = self.create_custom_filename(title, ext)
        await self.handle_file(src, scrape_item, filename, ext)

    async def _request_audio(self, url: AbsoluteHttpURL) -> tuple[str, AbsoluteHttpURL]:
        async with self.request(url) as resp:
            text = await resp.text()
            title = css.select_text(await resp.soup(), ".jp-title")

        src = _CDN.with_path(extr_text(text, _CDN.host, '"'))
        return title, src
