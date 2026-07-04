from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers._kvs import KernelVideoSharingCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL


class YourLesbiansCrawler(KernelVideoSharingCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://yourlesbians.com")
    DOMAIN: ClassVar[str] = "yourlesbians.com"
    FOLDER_DOMAIN: ClassVar[str] = "YourLesbians"
