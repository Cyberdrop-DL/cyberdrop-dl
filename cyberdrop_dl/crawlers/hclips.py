from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers._tubecorporate import TubeCorporateCrawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedDomains


class HClipsCrawler(TubeCorporateCrawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = ("privatehomeclips.com",)
    DOMAIN: ClassVar[str] = "hclips"
    FOLDER_DOMAIN: ClassVar[str] = "HClips"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://hclips.com")
