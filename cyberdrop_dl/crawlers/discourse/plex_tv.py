from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers.discourse import DiscourseCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL


class PlexTVCrawler(DiscourseCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://forums.plex.tv")
    DOMAIN: ClassVar[str] = PRIMARY_URL.host
