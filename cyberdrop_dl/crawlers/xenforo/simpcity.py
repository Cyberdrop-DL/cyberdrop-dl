from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.network import etag
from cyberdrop_dl.network.http import HTTPConfig
from cyberdrop_dl.url_objects import AbsoluteHttpURL

from .xenforo import XenforoCrawler

etag.register(etag.ETag("65b7753c-528a", "SC Scrape Image"))


@HTTPConfig(rate_limit=(1, 2))
class SimpCityCrawler(XenforoCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://simpcity.cr")
    DOMAIN: ClassVar[str] = "simpcity"
    FOLDER_DOMAIN: ClassVar[str] = "SimpCity"
    LOGIN_USER_COOKIE_NAME: ClassVar[str] = "ogaddgmetaprof_user"
    login_required: ClassVar[bool | None] = False
    IGNORE_EMBEDED_IMAGES_SRC: ClassVar[bool] = True
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("simpcity.su",)
