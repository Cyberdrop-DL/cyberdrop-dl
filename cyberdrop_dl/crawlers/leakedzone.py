from __future__ import annotations

import binascii
from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar, Literal, final

from cyberdrop_dl import aio
from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text
from cyberdrop_dl.utils.dataclass import struct
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem

_PREMIUM_ONLY = "This creator's media is for Premium members only"


@final
class Selector:
    JW_PLAYER = "script:-soup-contains('playerInstance.setup')"
    IMAGE = "[data-fancybox] img"
    PREMIUM_OVERLAY = "div.premium-lock-overlay"
    THUMB = "#media-player img"
    NEXT_PAGE = "a.page-btn[rel=next]"
    PROFILE_MEDIA = (
        "#media "
        + css.where(
            "#media-items-videos",
            "#media-items-photos",
            "#media-items-shorts",
        )
        + " > a[href]"
    )


@struct
class Post:
    id: str
    type: Literal["video", "image", "short"]
    src: str
    thumb: str | None = None


@HTTPConfig(rate_limit=(3, 10))
class LeakedZoneCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/<model_id>/video/<video_id>",
        "Short": "/<model_id>/short/<short_id>",
        "Photo": "/<model_id>/photo/<short_id>",
        "Model videos": "/<model_id>",
        "Model shorts": "/<model_id>/short",
        "Model photos": "/<model_id>/photo",
    }
    DOMAIN: ClassVar[str] = "leakedzone"
    FOLDER_DOMAIN: ClassVar[str] = "LeakedZone"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://leakedzone.com")
    NEXT_PAGE_SELECTOR: ClassVar[str] = Selector.NEXT_PAGE

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [model, *rest]:
                match rest:
                    case ["video", post_id]:
                        await self.video(scrape_item, model, post_id)
                    case ["short", post_id]:
                        await self.short(scrape_item, model, post_id)
                    case ["photo", post_id]:
                        await self.image(scrape_item, model, post_id)
                    case [] | ["short"]:
                        await self.model(scrape_item, model)
                    case ["photo"]:
                        await self.model(scrape_item, model, photos=True)
                    case _:
                        raise ValueError
            case _:
                raise ValueError

    @classmethod
    def _extract_video(cls, soup: BeautifulSoup, post_id: str) -> Post:
        try:
            js_text = css.select_text(soup, Selector.JW_PLAYER)
        except css.SelectorError:
            if not soup.select_one(Selector.PREMIUM_OVERLAY):
                raise
            raise ScrapeError(HTTPStatus.PAYMENT_REQUIRED, _PREMIUM_ONLY) from None

        return Post(
            id=post_id,
            type="video",
            src=_decode_video_url(extr_text(js_text, 'file: f("', '"),')),
            thumb=css.select(soup, "#media-player img", "src"),
        )

    @classmethod
    def _extract_short(cls, soup: BeautifulSoup, post_id: str) -> Post:
        try:
            video = css.select(soup, f"video[aria-label*='#{post_id}']")
        except css.SelectorError:
            if not soup.select_one(Selector.PREMIUM_OVERLAY):
                raise
            raise ScrapeError(HTTPStatus.PAYMENT_REQUIRED, _PREMIUM_ONLY) from None

        return Post(
            id=post_id,
            type="short",
            src=_decode_video_url(css.attr(video, "data-src")),
            thumb=css.attr(video, "poster"),
        )

    @classmethod
    def _extract_image(cls, soup: BeautifulSoup, post_id: str) -> Post:
        try:
            src = css.select(soup, Selector.IMAGE, "src")
        except css.SelectorError:
            ol = css.select(soup, Selector.PREMIUM_OVERLAY)
            assert ol.parent
            src = css.select(ol.parent, "img", "src")

        return Post(
            id=post_id,
            type="image",
            src=src,
            thumb=None,
        )

    @error_handling_wrapper
    async def model(self, scrape_item: ScrapeItem, model: str, *, photos: bool = False) -> None:
        soup = await self.request_soup(scrape_item.url)
        scrape_item.setup_as_profile("")

        soup, pages = await aio.peek_next(self.web_pager(scrape_item.url))
        if soup.select_one(Selector.PREMIUM_OVERLAY):
            if not photos:
                photos_url = self.PRIMARY_URL / model / "photo"
                exc = ScrapeError(HTTPStatus.PAYMENT_REQUIRED, _PREMIUM_ONLY)
                exc.add_note(f"You can use '{photos_url}' as input to download photos, even without premium")
                raise exc

            self.log.warning(f"{_PREMIUM_ONLY}. Trying to download photos")

        sleep = aio.periodic_sleep(10)
        async for soup in pages:
            for new_item in self.iter_children(scrape_item, soup, Selector.PROFILE_MEDIA):
                self.create_task(self.run(new_item))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, model: str, post_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        scrape_item.setup_as_album(self.create_title(f"@{model}"))
        scrape_item.append_folders("videos")
        post = self._extract_video(soup, post_id)
        await self._video(scrape_item, post)

    @error_handling_wrapper
    async def short(self, scrape_item: ScrapeItem, model: str, post_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        scrape_item.setup_as_album(self.create_title(f"@{model}"))
        scrape_item.append_folders("shorts")
        post = self._extract_short(soup, post_id)
        await self._video(scrape_item, post)

    async def _video(self, scrape_item: ScrapeItem, post: Post) -> None:
        src = self.parse_url(post.src)
        async with self.downloader.lock(src):
            m3u8, _ = await self.request_m3u8(src)

        filename, ext = self.get_filename_and_ext(f"{post.id}.mp4")
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            filename,
            ext,
            m3u8=m3u8,
            thumbnail=post.thumb,
            metadata=post,
        )

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem, model: str, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        scrape_item.setup_as_album(self.create_title(f"@{model}"))
        scrape_item.append_folders("photos")
        post = self._extract_image(soup, video_id)
        src = self.parse_url(post.src)
        if stem := src.name.rpartition("_")[0]:
            src = src.with_name(stem + src.suffix)
        filename, ext = self.get_filename_and_ext(src.name)
        await self.handle_file(
            src,
            scrape_item,
            filename,
            ext,
            custom_filename=self.create_custom_filename(filename, ext, file_id=post.id),
            metadata=post,
        )


def _decode_video_url(url: str) -> str:
    # cut first and last 16 characters, reverse, base64 decode
    return binascii.a2b_base64(url[-17:15:-1]).decode()
