from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, override

from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.constants import CDL_USER_AGENT
from cyberdrop_dl.crawlers.crawler import DownloadConfig
from cyberdrop_dl.crawlers.kemono.api import KemonoAPI
from cyberdrop_dl.crawlers.kemono.kemono import KemonoBaseCrawler
from cyberdrop_dl.crawlers.kemono.models import UserPostModel
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.config.crawlers import KemonoConfig
    from cyberdrop_dl.crawlers.crawler import SupportedPaths


class PawchiveAPI(KemonoAPI[UserPostModel]):
    # https://pawchive.pw/api/swagger_schema
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pawchive.pw/api/v1")
    CDN: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://file.pawchive.pw")

    async def revisions(self, service: str, creator_id: str, post_id: str) -> dict[int, dict[str, Any]]:
        url = self.ENTRYPOINT / service / "user" / creator_id / "post" / post_id / "revisions"
        resp = await self.request_json(url)

        def parse(post: dict[str, Any]) -> dict[str, Any]:
            post.setdefault("user_id", creator_id)
            post.setdefault("service", service)
            return post

        return {p["revision_id"]: p for p in map(parse, resp)}


@HTTPConfig(rate_limit=(3, 1), headers={"User-Agent": CDL_USER_AGENT})
@DownloadConfig(slots=5)
class PawchiveCrawler(KemonoBaseCrawler[PawchiveAPI]):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = KemonoBaseCrawler.SUPPORTED_PATHS | {
        "Revision": "/<service>/user/<user_id>/post/<post_id>/revision/<revision_id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pawchive.pw")
    DOMAIN: ClassVar[str] = "pawchive"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("pawchive.st",)

    def __post_init__(self) -> None:
        self.api: PawchiveAPI = PawchiveAPI.from_crawler(self)

    @property
    @override
    def __kemono_config__(self) -> KemonoConfig:
        return self.config.crawlers.pawchive

    @override
    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [service, "user", creator_id, "post", post_id, "revision", revision_id]:
                await self.revision(scrape_item, service, creator_id, post_id, int(revision_id))
            case _:
                await super().fetch(scrape_item)

    @error_handling_wrapper
    async def revision(
        self, scrape_item: ScrapeItem, service: str, creator_id: str, post_id: str, revision_id: int
    ) -> None:
        revisions = await self.api.revisions(service, creator_id, post_id)
        rev = revisions.get(revision_id)
        if not rev:
            raise ScrapeError(404, f"{revision_id = } not found") from None

        post = self.api.__post__.model_validate(rev)
        await self._user_post(scrape_item, post)  # pyright: ignore[reportArgumentType]
