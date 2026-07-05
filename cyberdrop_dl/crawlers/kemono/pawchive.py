from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl.crawlers.kemono.api import KemonoAPI
from cyberdrop_dl.crawlers.kemono.kemono import KemonoBaseCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from cyberdrop_dl.config.crawlers import KemonoConfig


class PawchiveAPI(KemonoAPI):
    # https://pawchive.pw/api/swagger_schema
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pawchive.pw/api/v1")


class PawchiveCrawler(KemonoBaseCrawler):
    __kemono_api__: ClassVar[type[KemonoAPI]] = PawchiveAPI
    __kemono_cdn__: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://file.pawchive.pw")

    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pawchive.pw")
    DOMAIN: ClassVar[str] = "pawchive"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("pawchive.st",)

    @property
    @override
    def __kemono_config__(self) -> KemonoConfig:
        return self.config.crawlers.pawchive
