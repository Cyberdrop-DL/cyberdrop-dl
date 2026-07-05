from __future__ import annotations

from typing import ClassVar

from cyberdrop_dl.crawlers.kemono.api import KemonoAPI
from cyberdrop_dl.crawlers.kemono.kemono import KemonoBaseCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL


class PawchiveAPI(KemonoAPI):
    # https://pawchive.pw/api/swagger_schema
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pawchive.pw/api/v1")
    CDN: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://file.pawchive.pw")


class Pawchive(KemonoBaseCrawler):
    __kemono_api__: ClassVar[type[KemonoAPI]] = PawchiveAPI
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pawchive.pw/api/v1")
    DOMAIN: ClassVar[str] = "pawchive"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("pawchive.st",)
