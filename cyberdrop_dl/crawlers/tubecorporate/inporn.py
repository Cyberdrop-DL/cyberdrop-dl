from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers.tubecorporate import TubeCorporateCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL


class InPornCrawler(TubeCorporateCrawler):
    DOMAIN: ClassVar[str] = "inporn"
    FOLDER_DOMAIN: ClassVar[str] = "InPorn"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://inporn.com")
