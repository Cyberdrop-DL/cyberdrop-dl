from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL

from .kemono import KemonoBaseCrawler


class CoomerCrawler(KemonoBaseCrawler):
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://coomer.st")
    DOMAIN: ClassVar[str] = "coomer"
    API_ENTRYPOINT = AbsoluteHttpURL("https://coomer.st/api/v1")
    SERVICES = "onlyfans", "fansly", "candfans"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = "coomer.party", "coomer.su"

    @property
    def session_cookie(self) -> str:
        return self.manager.config_manager.authentication_data.coomer.session
