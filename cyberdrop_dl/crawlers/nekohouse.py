from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.url_objects import AbsoluteHttpURL

from .kemono import KemonoBaseCrawler

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import SupportedPaths


class NekohouseCrawler(KemonoBaseCrawler, is_debug=True):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Model": "/<service>/user/<user_id>",
        "Individual Post": "/<service>/user/<user_id>/post/<post_id>",
        "Direct links": "/(data|thumbnails)/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://nekohouse.su")
    DOMAIN: ClassVar[str] = "nekohouse"
    SERVICES = "fanbox", "fantia", "fantia_products", "subscribestar", "twitter"

    async def __async_post_init__(self) -> None:
        await super().__async_post_init__()
        # Only this API endpoint is available
        await self._get_usernames(self.PRIMARY_URL / "api/creators")
