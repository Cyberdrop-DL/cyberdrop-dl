from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers._tubecorporate import TubeCorporateCrawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL


class FuXXXCrawler(TubeCorporateCrawler):
    DOMAIN: ClassVar[str] = "fuxxx"
    FOLDER_DOMAIN: ClassVar[str] = "FuXXX"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://fuxxx.com")
