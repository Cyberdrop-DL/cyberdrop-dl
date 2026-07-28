from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers.crawler import DownloadConfig
from cyberdrop_dl.url_objects import AbsoluteHttpURL

from ._yetishare import YetiShareCrawler


@DownloadConfig(slots=1)
class CyberfileCrawler(YetiShareCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://cyberfile.me/")
    DOMAIN: ClassVar[str] = "cyberfile"
