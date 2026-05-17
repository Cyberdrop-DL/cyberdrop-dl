from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers.tubecorporate import TubeCorporateCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL


class VJavCrawler(TubeCorporateCrawler):
    DOMAIN: ClassVar[str] = "vjav"
    FOLDER_DOMAIN: ClassVar[str] = "VJav"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vjav.com")
