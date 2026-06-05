from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers._chevereto import CheveretoCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL


class ImgLikeCrawler(CheveretoCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://imglike.com")
    DOMAIN: ClassVar[str] = "imglike.com"
    FOLDER_DOMAIN: ClassVar[str] = "ImgLike"
