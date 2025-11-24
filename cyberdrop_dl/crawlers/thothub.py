from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers._kvs import KernelVideoSharingCrawler
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL


class ThotHubCrawler(KernelVideoSharingCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://thothub.to")
    DEFAULT_TRIM_URLS: ClassVar[bool] = False
    DOMAIN: ClassVar[str] = "thothub"
    FOLDER_DOMAIN: ClassVar[str] = "ThotHub"
