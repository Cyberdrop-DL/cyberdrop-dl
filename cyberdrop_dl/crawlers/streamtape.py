from __future__ import annotations

import dataclasses
import re
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


PRIMARY_URL = AbsoluteHttpURL("https://streamtape.com")


class RegexSelectors:
    url_parts = re.compile(r"['\"]/+(.*?)['\"].*?\(['\"](.*?)['\"]\)")
    url_part_removals = re.compile(r"substring\((\d+)\)")


@dataclasses.dataclass(frozen=True, slots=True)
class LinkComponents:
    part_one: str
    part_two: str
    removals: int


_REGEX_SELECTORS = RegexSelectors()


class StreamtapeCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {"Videos": "/v/", "Player": "/e/"}
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "streamtape.com"
    FOLDER_DOMAIN: ClassVar[str] = "Streamtape"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if scrape_item.url.parts[1] in ("e", "v"):
            return await self.video(scrape_item)
        else:
            raise ValueError

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem) -> None:
        scrape_item.url = await self.create_canonical_url(scrape_item)
        if await self.check_complete_from_referer(scrape_item):
            return
        soup = await self.request_soup(scrape_item.url)
        scripts = soup.find_all("script")[::-1]
        for script in scripts:
            if "document.getElementById('ideoooolink').innerHTML" in script.text:
                break
        else:
            raise RuntimeError("Could not find video script")
        generator_url = await self.decode_links(script.text)
        download_url = await self._get_redirect_url(generator_url)
        filename, ext = self.get_filename_and_ext(download_url.name)

        return await self.handle_file(download_url, scrape_item, filename, ext)

    async def decode_links(self, javascript: str) -> AbsoluteHttpURL:
        scripts = javascript.split(";")[:-1]
        encoded_links: list[LinkComponents] = []
        decoded_links: list[AbsoluteHttpURL] = []
        for script in scripts:
            script = script.strip()
            parts = _REGEX_SELECTORS.url_parts.search(script)
            removals = _REGEX_SELECTORS.url_part_removals.findall(script)
            if parts is not None:
                encoded_links.append(LinkComponents(parts.group(1), parts.group(2), sum(int(num) for num in removals)))
        for parts in encoded_links:
            decoded_link = parts.part_one + parts.part_two[parts.removals :]
            if decoded_link.startswith("streamtape.com/get_video?id="):
                decoded_links.append(self.parse_url(f"https://{decoded_link}"))
        return max(set(decoded_links), key=decoded_links.count)

    async def create_canonical_url(self, scrape_item: ScrapeItem) -> AbsoluteHttpURL:
        return self.parse_url(f"https://{scrape_item.url.host}/v/{scrape_item.url.parts[2]}")
