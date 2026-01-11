from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers._tubecorporate import TubeCorporateCrawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL


class HotMovsCrawler(TubeCorporateCrawler):
    DOMAIN: ClassVar[str] = "hotmovs"
    FOLDER_DOMAIN: ClassVar[str] = "HotMovs"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://hotmovs.com")
