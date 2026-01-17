from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers._tubecorporate import TubeCorporateCrawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL


class TubePornClassicCrawler(TubeCorporateCrawler):
    DOMAIN: ClassVar[str] = "tubepornclassic"
    FOLDER_DOMAIN: ClassVar[str] = "TubePornClassic"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://tubepornclassic.com")
