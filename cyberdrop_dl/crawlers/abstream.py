from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers._xfs import EmbedOnlyMixin, XVideoSharingCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL


class ABStreamCrawler(EmbedOnlyMixin, XVideoSharingCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://abstream.to")
    DOMAIN: ClassVar[str] = "abstream"
    FOLDER_DOMAIN: ClassVar[str] = "ABStream"
    NEEDS_REFERER: ClassVar[bool] = True
