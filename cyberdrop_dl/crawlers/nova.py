from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl.crawlers.pixeldrain import PixelDrainAPI, PixelDrainCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import basic_auth

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedDomains, SupportedPaths
    from cyberdrop_dl.url_objects import ScrapeItem


class NovaStorageCrawler(PixelDrainCrawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = ()
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Filesystem": (
            "/d/<id>",
            "/api/filesystem/<path>...",
        ),
        "**NOTE**": "text files will not be downloaded but their content will be parsed for URLs",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://nova.storage")
    DOMAIN: ClassVar[str] = "nova.storage"
    FOLDER_DOMAIN: ClassVar[str] = "Nova"

    def __post_init__(self) -> None:
        self.api: NovaAPI = NovaAPI.from_crawler(self)  # pyright: ignore[reportIncompatibleVariableOverride]
        if self.api.logged_in:
            self.downloader.slots = None

    @override
    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if self.origin.host != self.PRIMARY_URL.host:
            raise ValueError
        match scrape_item.url.parts[1:]:
            case ["d", *path] if path:
                return await self.filesystem(scrape_item, "/".join(path))
            case _:
                raise ValueError


class NovaAPI(PixelDrainAPI):
    def __post_init__(self) -> None:
        self.headers: dict[str, str] = {}
        if api_key := self.config.auth.nova.api_key:
            self.headers["Authorization"] = basic_auth("Cyberdrop-DL", api_key)
