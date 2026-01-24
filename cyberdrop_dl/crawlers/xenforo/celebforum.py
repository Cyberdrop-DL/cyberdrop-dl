from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL

from .xenforo import XenforoCrawler

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import RateLimit


class CelebForumCrawler(XenforoCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://celebforum.to")
    DOMAIN: ClassVar[str] = "celebforum"
    FOLDER_DOMAIN: ClassVar[str] = "CelebForum"
    IGNORE_EMBEDED_IMAGES_SRC: ClassVar = True  # images src is always a thumbnail
    _IMPERSONATE: ClassVar[str | bool | None] = True
    _RATE_LIMIT: ClassVar[RateLimit] = 3, 10

    @classmethod
    def is_thumbnail(cls, link: AbsoluteHttpURL) -> bool:
        if link.host == cls.PRIMARY_URL.host:
            if all(part in link.parts for part in ["data", "attachments"]):  # Thumbnails
                return True
            if all(part in link.parts for part in ["data", "assets"]):  # Placeholder content for insufficient rank
                return True
        return False
