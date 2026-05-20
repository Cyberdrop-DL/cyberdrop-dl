from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.crawlers.vbulletin import vBulletinCrawler
from cyberdrop_dl.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import RateLimit, SupportedDomains


class ViperGirlsCrawler(vBulletinCrawler):
    login_required: ClassVar[bool] = False
    VBULLETIN_LOGIN_COOKIE_NAME: ClassVar[str] = "vg_password"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vipergirls.to")
    DOMAIN: ClassVar[str] = "vipergirls.to"
    FOLDER_DOMAIN: ClassVar[str] = "ViperGirls"
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "viper.click", "vipergirls.to"
    VBULLETIN_API_ENDPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://viper.click/vr.php")
    _RATE_LIMIT: ClassVar[RateLimit] = 4, 1
