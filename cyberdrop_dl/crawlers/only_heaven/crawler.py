from __future__ import annotations

import dataclasses
from collections.abc import Generator
from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl.crawlers.kemono.api import KemonoAPI
from cyberdrop_dl.crawlers.kemono.kemono import KemonoBaseCrawler
from cyberdrop_dl.crawlers.only_heaven.models import File, UserPostModel
from cyberdrop_dl.exceptions import NoExtensionError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import unique
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    import logging
    from collections.abc import Generator

    from cyberdrop_dl.config.crawlers import KemonoConfig
    from cyberdrop_dl.crawlers.crawler import SupportedDomains, SupportedPaths
    from cyberdrop_dl.url_objects import ScrapeItem


class OnlyHavenAPI(KemonoAPI[UserPostModel]):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://cum.st/api/v1")
    VALID_QUERY_PARAMS: ClassVar[set[str]] = KemonoAPI.VALID_QUERY_PARAMS | {"type"}
    __post__: type[UserPostModel] = UserPostModel

    async def dm(self, service: str, creator_id: str, dm_id: str) -> UserPostModel:
        url = self.ENTRYPOINT / service / "user" / creator_id / "dm" / dm_id
        resp = await self.request_json(url)
        post = resp.get("post", resp)
        post.setdefault("user_id", creator_id)
        post.setdefault("service", service)
        return self.__post__.model_validate(post)


class OnlyHavenCrawler(KemonoBaseCrawler):
    __kemono_api__: ClassVar[type[OnlyHavenAPI]] = OnlyHavenAPI  # pyright: ignore[reportIncompatibleVariableOverride]
    __kemono_cdn__: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://e1.cum.st")

    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = ("cum.st",)
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://cum.st")
    DOMAIN: ClassVar[str] = "onlyhaven"
    FOLDER_DOMAIN: ClassVar[str] = "OnlyHaven"

    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Post": "/creators/<service>/<user_id>/post/<post_id>",
        "DM": "/creators/<service>/<user_id>/dm/<dm_id>",
        "Creator": "/creators/<service>/<user_id>",
        "Post Search": "/search?q=...",
    }
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date} - {id}"

    def __post_init__(self) -> None:
        self.api: OnlyHavenAPI = self.__kemono_api__.from_crawler(self)  # pyright: ignore[reportIncompatibleVariableOverride]

    @property
    @override
    def __kemono_config__(self) -> KemonoConfig:
        return self.config.crawlers.only_haven

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["creators", service, creator_id, "post", post_id]:
                return await self.post(scrape_item, service, creator_id, post_id)
            case ["creators", service, creator_id, "dm", dm_id]:
                return await self.dm(scrape_item, service, creator_id, dm_id)
            case ["creators", service, creator_id]:
                return await self.creator(scrape_item, service, creator_id)
            case ["posts"] if search_query := scrape_item.url.query.get("q"):
                return await self.search(scrape_item, search_query)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def dm(self, scrape_item: ScrapeItem, service: str, creator_id: str, dm_id: str) -> None:
        post = await self.api.dm(service, creator_id, dm_id)
        await self._user_post(scrape_item, post)  # pyright: ignore[reportArgumentType]

    @error_handling_wrapper
    async def _direct_file(self, scrape_item: ScrapeItem, url: AbsoluteHttpURL | None = None) -> None:
        link = url or scrape_item.url
        checksum = link.parent.name
        if await self.check_complete_by_hash(link, "sha256", checksum):
            return

        name = link.query.get("f") or link.name
        try:
            filename, ext = self.get_filename_and_ext(name)
        except NoExtensionError:
            # Some patreon URLs have another URL as the filename:
            # ex: https://kemono.su/data/7a...27ad7e40bd.jpg?f=https://www.patreon.com/media-u/Z0F..00672794_
            filename, ext = self.get_filename_and_ext(link.name)

        await self.handle_file(link, scrape_item, name, ext, custom_filename=filename)

    @override
    def _post(self, scrape_item: ScrapeItem, post: UserPostModel) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        scrape_item.uploaded_at = post.timestamp
        self.create_eager_task(self.write_metadata(scrape_item, f"post_{post.id}", post))
        files = FileFilterer(post, self.__kemono_config__, self.log)
        try:
            self._extract_post_files(scrape_item, files)
        finally:
            self.tui.files.stats.skipped += files.skipped
        self._extract_urls_from_post_content(scrape_item, post)

    @override
    def _extract_post_files(self, scrape_item: ScrapeItem, post_files: FileFilterer) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        for url in unique(map(self._compose_file_url, post_files)):
            self.create_eager_task(self._direct_file(scrape_item, url))
            scrape_item.add_children()

    @override
    def _compose_file_url(self, file: File) -> AbsoluteHttpURL:  # pyright: ignore[reportIncompatibleMethodOverride]
        url = self.__kemono_cdn__ / "media" / file.storageKey / max(file.variants).name
        return url.update_query(f=file.name)


@dataclasses.dataclass(slots=True)
class FileFilterer:
    post: UserPostModel
    config: KemonoConfig
    log: logging.LoggerAdapter[logging.Logger] | logging.Logger
    skipped: int = dataclasses.field(init=False, default=0)

    def _files(self) -> Generator[tuple[File, str, bool]]:
        for file in self.post.attachments:
            yield file, "attachment", self.config.attachments

    def __iter__(self) -> Generator[File]:
        for file, kind, should_download in self._files():
            file_name = file.name
            if not should_download:
                self._report_skip_by_config(file_name, kind)
            else:
                yield file

    def _report_skip_by_config(self, name: str, kind: str) -> None:
        self.log.info("Skipping file '%s' in post #%s by config options [%s]", name, self.post.id, kind)
        self.skipped += 1
