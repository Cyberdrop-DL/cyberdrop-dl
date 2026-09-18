from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, ClassVar, override

from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.constants import CDL_USER_AGENT
from cyberdrop_dl.crawlers.crawler import DownloadConfig
from cyberdrop_dl.crawlers.kemono.api import KemonoAPI
from cyberdrop_dl.crawlers.kemono.kemono import FileFilterer, KemonoBaseCrawler
from cyberdrop_dl.crawlers.kemono.models import PostModel, UserPostModel
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Iterable

    import bs4

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
        url = scrape_item.url
        if self.is_subdomain(url) and url.host.startswith("t"):  # ex: t1.pawchive.pw
            await self._temp_file(scrape_item)
            return

        match url.parts[1:]:
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
        await self._user_post(scrape_item, post)

    @override
    async def _extract_post_files(self, scrape_item: ScrapeItem, post_files: FileFilterer) -> None:
        await super()._extract_post_files(scrape_item, post_files)

        if not post_files.has_deferred_files:
            return

        post = post_files.post
        if not self.__kemono_config__.expand_posts:
            self.log.warning("Post %s has deferred files but `expand_posts` is disabled. Ignoring..", post.id)
            return

        await self._deferred_files(scrape_item, post)

    async def _deferred_files(self, scrape_item: ScrapeItem, post: PostModel) -> None:
        self.log.info("Trying to get temp download URLs for deferred files in post %s", post.id)
        soup = await self.request_soup(scrape_item.url)
        files = await asyncio.to_thread(lambda: tuple(_extract_deferred_files(soup)))
        if not files:
            self.log.warning("Did not find any deferred URL for post %", post.id)
            return

        async with self.new_task_group() as tg:
            for name, src in files:
                self.log.info("Found temp deferred file '%s' (%s)", name, src)
                tg.create_task(self._temp_file(scrape_item, src, name))

    async def _temp_file(
        self, scrape_item: ScrapeItem, src: AbsoluteHttpURL | None = None, name: str | None = None
    ) -> None:
        src = src or scrape_item.url
        name = name or src.name
        with self.catch_errors(src):
            if src.suffix == ".m3u8":
                await self._m3u8(scrape_item, src, name)
                return

            filename, ext = self.get_filename_and_ext(name)
            await self.handle_file(src, scrape_item, name, ext, custom_filename=filename)

    async def _m3u8(self, scrape_item: ScrapeItem, url: AbsoluteHttpURL, name: str) -> None:
        if await self.check_complete(url):
            return

        m3u8, info = await self.request_m3u8(url)
        await self.handle_file(
            url,
            scrape_item,
            name,
            ext := ".mp4",
            m3u8=m3u8,
            custom_filename=self.create_custom_filename(
                name,
                ext,
                resolution=info and info.resolution,
                video_codec=info and info.codecs.video,
                audio_codec=info and info.codecs.audio,
            ),
        )


def _extract_deferred_files(soup: bs4.Tag) -> Iterable[tuple[str, AbsoluteHttpURL]]:
    body = css.select(soup, ".post__body")
    deferred_span = "span.post__relay-clock"
    for li in css.iselect(body, "li:has(source)"):
        try:
            summary = css.select(li, f"summary:has({deferred_span})")
        except css.SelectorError:
            continue
        else:
            name = css.text(summary)
            src = css.select(li, "source", "src")
            yield name, PawchiveCrawler.parse_url(src)

    for li in css.iselect(body, f"li.post__attachment:has({deferred_span})"):
        attach = css.select(li, "a.post__attachment-link")
        name = css.text(attach).removeprefix("Download ")
        src = css.attr(attach, "href")
        yield name, PawchiveCrawler.parse_url(src)
