from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.url_objects import AbsoluteHttpURL

from .kemono import KemonoBaseCrawler


class CoomerCrawler(KemonoBaseCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://coomer.st")
    DOMAIN: ClassVar[str] = "coomer"
    API_ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://coomer.st/api/v1")
    SERVICES: ClassVar[tuple[str, ...]] = "onlyfans", "fansly", "candfans"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = "coomer.party", "coomer.su"

    @property
    def session_cookie(self) -> str:
        return self.config.auth.coomer.session
