from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers._tubecorporate import TubeCorporateCrawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL


class UPorniaCrawler(TubeCorporateCrawler):
    DOMAIN: ClassVar[str] = "upornia"
    FOLDER_DOMAIN: ClassVar[str] = "UPornia"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://upornia.com")
