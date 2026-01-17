from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers._tubecorporate import TubeCorporateCrawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL


class TXXXCrawler(TubeCorporateCrawler):
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("videotxxx.com",)
    DOMAIN: ClassVar[str] = "txxx"
    FOLDER_DOMAIN: ClassVar[str] = "TXXX"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://txxx.com")
