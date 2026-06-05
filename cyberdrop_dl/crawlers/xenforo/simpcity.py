from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.url_objects import AbsoluteHttpURL

from .xenforo import XenforoCrawler

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import RateLimit


class SimpCityCrawler(XenforoCrawler, is_debug=True):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://simpcity.cr")
    DOMAIN: ClassVar[str] = "simpcity"
    FOLDER_DOMAIN: ClassVar[str] = "SimpCity"
    LOGIN_USER_COOKIE_NAME: ClassVar[str] = "ogaddgmetaprof_user"
    login_required: bool = False
    IGNORE_EMBEDED_IMAGES_SRC: ClassVar[bool] = False
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("simpcity.su",)
    _RATE_LIMIT: ClassVar[RateLimit] = 1, 20
