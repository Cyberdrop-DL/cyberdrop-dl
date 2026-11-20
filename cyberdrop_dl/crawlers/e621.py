from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.constants import CDL_USER_AGENT
from cyberdrop_dl.crawlers.danbooru import DanBooruGenericCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedPaths


@HTTPConfig(headers={"User-Agent": f"{CDL_USER_AGENT} (by B05FDD249DF29ED3)"})
class E621Crawler(DanBooruGenericCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = DanBooruGenericCrawler.SUPPORTED_PATHS | {
        "Post": ("/post/<post_id>",),
        "Pools": ("/pool/<pool_id>",),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://e621.net")
    DOMAIN: ClassVar[str] = "e621.net"
    FOLDER_DOMAIN: ClassVar[str] = "E621"
    CDN: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://static1.e621.net")


class BlepArtCrawler(DanBooruGenericCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = DanBooruGenericCrawler.SUPPORTED_PATHS | {
        "Post": "/posts/<post_id>",
        "Pools": "/pools/<pool_id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://blep.art")
    DOMAIN: ClassVar[str] = "blep.art"
    FOLDER_DOMAIN: ClassVar[str] = "BlepArt"
    CDN: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://cdn.blep.art")


class HmofaCrawler(DanBooruGenericCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = DanBooruGenericCrawler.SUPPORTED_PATHS | {
        "Post": ("/post/<post_id>",),
        "Pools": ("/pools/<pool_id>",),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://hmofa.gallery")
    DOMAIN: ClassVar[str] = "hmofa.gallery"
    FOLDER_DOMAIN: ClassVar[str] = "Hmofa"
    CDN: ClassVar[AbsoluteHttpURL] = PRIMARY_URL


class E926Crawler(DanBooruGenericCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = DanBooruGenericCrawler.SUPPORTED_PATHS | {
        "Post": ("/posts/<post_id>",),
        "Pools": ("/pools/<pool_id>",),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://e926.net")
    DOMAIN: ClassVar[str] = "e926.net"
    FOLDER_DOMAIN: ClassVar[str] = "E926"
    CDN: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://static1.e926.net")


class FloofgensCrawler(DanBooruGenericCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = DanBooruGenericCrawler.SUPPORTED_PATHS | {
        "Post": ("/posts/<post_id>",),
        "Pools": ("/pools/<pool_id>",),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://floofgens.net")
    DOMAIN: ClassVar[str] = "floofgens.net"
    FOLDER_DOMAIN: ClassVar[str] = "Floofgens"
    CDN: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://static1.floofgens.net")
