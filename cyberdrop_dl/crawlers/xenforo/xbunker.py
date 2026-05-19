from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.url_objects import AbsoluteHttpURL

from .xenforo import XenforoCrawler


class XBunkerCrawler(XenforoCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://xbunker.cc")
    DOMAIN: ClassVar[str] = "xbunker"
    FOLDER_DOMAIN: ClassVar[str] = "XBunker"
