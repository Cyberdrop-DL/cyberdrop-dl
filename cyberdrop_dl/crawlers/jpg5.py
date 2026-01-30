from __future__ import annotations

import base64
from typing import TYPE_CHECKING, ClassVar, Final

from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils.utilities import error_handling_wrapper, xor_decrypt

from ._chevereto import CheveretoCrawler

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import RateLimit, SupportedDomains

_CDN: Final = "selti-delivery.ru"
_DECRYPTION_KEY: Final = b"seltilovessimpcity@simpcityhatesscrapers"


class JPG5Crawler(CheveretoCrawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "selti-delivery.ru", "jpg7.cr", "jpg6.su"
    DOMAIN: ClassVar[str] = "jpg5.su"
    FOLDER_DOMAIN: ClassVar[str] = "JPG5"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://jpg6.su")
    CHEVERETO_SUPPORTS_VIDEO: ClassVar[bool] = False
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = (
        "host.church",
        "jpg.homes",
        "jpg.church",
        "jpg.fish",
        "jpg.fishing",
        "jpg.pet",
        "jpeg.pet",
        "jpg1.su",
        "jpg2.su",
        "jpg3.su",
        "jpg4.su",
        "jpg5.su",
    )

    _RATE_LIMIT: ClassVar[RateLimit] = 2, 1

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        if cls.is_subdomain(url):
            # old jpg5 subdomains are still valid. ex: simp4.jpg5.su
            return url.with_host(url.host.replace("jpg6.su", "jpg5.su"))
        return url

    @error_handling_wrapper
    async def direct_file(
        self, scrape_item: ScrapeItem, url: AbsoluteHttpURL | None = None, assume_ext: str | None = None
    ) -> None:
        link = url or scrape_item.url

        if self.is_subdomain(link) and not link.host.endswith(_CDN):
            server, *_ = link.host.rsplit(".", 2)
            link = link.with_host(f"{server}.{_CDN}")

        await super().direct_file(scrape_item, link, assume_ext)

    def parse_url(
        self, link_str: str, relative_to: AbsoluteHttpURL | None = None, *, trim: bool | None = None
    ) -> AbsoluteHttpURL:
        if not link_str.startswith("https") and not link_str.startswith("/"):
            encrypted_url = bytes.fromhex(base64.b64decode(link_str).decode())
            link_str = xor_decrypt(encrypted_url, _DECRYPTION_KEY)
        return super().parse_url(link_str, relative_to, trim=trim)


def fix_db_referer(referer: str) -> str:
    url = AbsoluteHttpURL(referer)
    return str(JPG5Crawler.transform_url(url))
