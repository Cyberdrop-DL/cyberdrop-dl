from __future__ import annotations

import binascii
import dataclasses
import itertools
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.compat import IntEnum
from cyberdrop_dl.crawlers.crawler import Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, error_handling_wrapper, extr_text

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.url_objects import ScrapeItem


class PostType(IntEnum):
    IMAGE = 0
    VIDEO = 1


class Selector:
    JW_PLAYER = "script:-soup-contains('playerInstance.setup')"
    MODEL_NAME_FROM_PROFILE = "div.actor-name > h1"
    MODEL_NAME_FROM_VIDEO = "h2.actor-title-port"
    MODEL_NAME = f"{MODEL_NAME_FROM_VIDEO}, {MODEL_NAME_FROM_PROFILE}"


@dataclasses.dataclass(slots=True)
class Post:
    id: str
    type: PostType
    created_at: str | None = None
    image: str = ""
    stream_url_play: str = ""

    @staticmethod
    def from_dict(post: dict[str, Any]) -> Post:
        return Post(
            id=str(post["id"]),
            type=PostType(post["type"]),
            created_at=post["created_at"],
            image=post["image"].replace("_thumb", ""),
            stream_url_play=post.get("stream_url_play", ""),
        )


class LeakedZoneCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/<model_id>/video/<video_id>",
        "Model": "/<model_id>",
    }
    DOMAIN: ClassVar[str] = "leakedzone"
    FOLDER_DOMAIN: ClassVar[str] = "LeakedZone"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://leakedzone.com")
    IMAGES_CDN: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://image-cdn.leakedzone.com/storage/")
    _RATE_LIMIT: ClassVar[RateLimit] = 3, 10

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_, "video", video_id]:
                return await self.video(scrape_item, video_id)
            case [_]:
                return await self.model(scrape_item)
            case _:
                raise ValueError

    @classmethod
    def _extract_video(cls, soup: BeautifulSoup) -> str:
        js_text = css.select_text(soup, Selector.JW_PLAYER)
        return extr_text(js_text, 'file: f("', '"),')

    @error_handling_wrapper
    async def model(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)
        model_name = css.select_text(soup, Selector.MODEL_NAME_FROM_PROFILE)
        scrape_item.setup_as_profile(self.create_title(model_name))

        async for posts in self.api_pager(scrape_item.url):
            for post in posts:
                if post.type is PostType.VIDEO:
                    post_url = self.PRIMARY_URL / model_name / "video" / post.id
                    self.create_task(self._video(scrape_item.create_child(post_url), post))
                else:
                    post_url = self.PRIMARY_URL / model_name / "photo" / post.id
                    self.create_task(self._image(scrape_item.create_child(post_url), post))
                scrape_item.add_children()

    async def api_pager(self, url: AbsoluteHttpURL) -> AsyncGenerator[tuple[Post, ...]]:
        for page in itertools.count(1):
            posts = tuple(
                map(
                    Post.from_dict,
                    await self.request_json(
                        url.with_query(page=page),
                        headers={
                            "X-Requested-With": "XMLHttpRequest",
                        },
                    ),
                )
            )
            yield posts
            if len(posts) < 48:
                break

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        soup = await self.request_soup(scrape_item.url)
        model_name = css.select_text(soup, Selector.MODEL_NAME)
        scrape_item.setup_as_album(self.create_title(model_name))
        encoded_url = self._extract_video(soup)
        post = Post(video_id, PostType.VIDEO, stream_url_play=encoded_url)
        await self._handle_video(scrape_item, post)

    @error_handling_wrapper
    async def _video(self, scrape_item: ScrapeItem, post: Post) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return
        await self._handle_video(scrape_item, post)

    async def _handle_video(self, scrape_item: ScrapeItem, post: Post) -> None:
        url = self.parse_url(_decode_video_url(post.stream_url_play))
        m3u8, _ = await self.request_m3u8(url)
        filename, ext = self.get_filename_and_ext(f"{post.id}.mp4")
        if post.created_at:
            scrape_item.uploaded_at = self.parse_iso_date(post.created_at)
        await self.handle_file(scrape_item.url, scrape_item, filename, ext, m3u8=m3u8)

    @error_handling_wrapper
    async def _image(self, scrape_item: ScrapeItem, post: Post) -> None:
        image_url = self.IMAGES_CDN / post.image
        filename, ext = self.get_filename_and_ext(image_url.name)
        assert post.created_at
        scrape_item.uploaded_at = self.parse_iso_date(post.created_at)
        custom_filename = self.create_custom_filename(filename, ext, file_id=post.id)
        await self.handle_file(image_url, scrape_item, filename, ext, custom_filename=custom_filename)


def _decode_video_url(url: str) -> str:
    # cut first and last 16 characters, reverse, base64 decode
    # TODO: Research if this work on any JW Player
    return binascii.a2b_base64(url[-17:15:-1]).decode()
