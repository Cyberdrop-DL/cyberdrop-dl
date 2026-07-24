from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.url_objects import AbsoluteHttpURL

from .xenforo import XenforoCrawler


@HTTPConfig(impersonate=True, rate_limit=(3, 10))
class CelebForumCrawler(XenforoCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://celebforum.cc")
    DOMAIN: ClassVar[str] = "celebforum"
    FOLDER_DOMAIN: ClassVar[str] = "CelebForum"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("celebforum.to", "celeb.su")
    IGNORE_EMBEDED_IMAGES_SRC: ClassVar[bool] = True  # images src is always a thumbnail

    @classmethod
    def is_thumbnail(cls, link: AbsoluteHttpURL) -> bool:
        if link.host == cls.PRIMARY_URL.host:
            if all(part in link.parts for part in ["data", "attachments"]):  # Thumbnails
                return True
            if all(part in link.parts for part in ["data", "assets"]):  # Placeholder content for insufficient rank
                return True
        return False
