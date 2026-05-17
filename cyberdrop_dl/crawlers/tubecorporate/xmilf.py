from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers.tubecorporate import TubeCorporateCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL


class XMilfCrawler(TubeCorporateCrawler):
    DOMAIN: ClassVar[str] = "xmilf"
    FOLDER_DOMAIN: ClassVar[str] = "XMilf"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://xmilf.com")
