from __future__ import annotations

import base64
from typing import TYPE_CHECKING, ClassVar, Final

from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import xor_decrypt
from cyberdrop_dl.utils.errors import error_handling_wrapper

from ._chevereto import CheveretoCrawler

if TYPE_CHECKING:
    import yarl

    from cyberdrop_dl.crawlers.crawler import RateLimit, SupportedDomains

_CDN: Final = "cuckcapital.cr"
_DECRYPTION_KEY: Final = b"seltilovessimpcity@simpcityhatesscrapers"


class JPG5Crawler(CheveretoCrawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "selti-delivery.ru", "jpg7.cr", "jpg6.su", _CDN
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
        self, scrape_item: ScrapeItem, /, url: AbsoluteHttpURL | None = None, assume_ext: str | None = None
    ) -> None:
        link = _fix_cdn(url or scrape_item.url)
        await super().direct_file(scrape_item, link, assume_ext)

    @classmethod
    def parse_url(
        cls, link_str: yarl.URL | str, relative_to: AbsoluteHttpURL | None = None, *, trim: bool | None = None
    ) -> AbsoluteHttpURL:
        if type(link_str) is str:
            link_str = _decode_url(link_str)
        return _fix_cdn(super().parse_url(link_str, relative_to, trim=trim))


def _decode_url(url: str) -> str:
    if url.startswith(("https:", "http:", "/")):
        return url
    encrypted_url = bytes.fromhex(base64.b64decode(url).decode())
    return xor_decrypt(encrypted_url, _DECRYPTION_KEY)


def _fix_cdn(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    if JPG5Crawler.is_subdomain(url) and not url.host.endswith(_CDN):
        server, *_ = url.host.rsplit(".", 2)
        return url.with_host(f"{server}.{_CDN}")
    return url
