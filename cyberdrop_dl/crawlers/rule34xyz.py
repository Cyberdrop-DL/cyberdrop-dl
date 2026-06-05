from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers.rule34vault import Rule34VaultCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL


class Rule34XYZCrawler(Rule34VaultCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://rule34.xyz")
    DOMAIN: ClassVar[str] = "rule34.xyz"
    FOLDER_DOMAIN: ClassVar[str] = "Rule34XYZ"
