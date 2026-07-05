from __future__ import annotations

import dataclasses
import itertools
from typing import TYPE_CHECKING, Any, ClassVar, Self

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import parse_url
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterable

    from cyberdrop_dl.url_objects import ScrapeItem


class GoonBoxCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Image": "/img/<image_id>",
        "Album": "/album/<album_id>",
    }

    DOMAIN: ClassVar[str] = "goonbox"
    FOLDER_DOMAIN: ClassVar[str] = "GoonBox"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://goonbox.cr")

    def __post_init__(self) -> None:
        self.api: GoonBoxAPI = GoonBoxAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["img", file_id]:
                return await self.image(scrape_item, file_id)
            case ["album", album_id]:
                return await self.image(scrape_item, album_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem, image_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        image = await self.api.image(image_id)
        await self._image(scrape_item, image)

    @error_handling_wrapper
    async def _image(self, scrape_item: ScrapeItem, image: Image) -> None:
        scrape_item.uploaded_at = self.parse_iso_date(image.created_at)
        name = image.original_filename or image.src.name
        filename, ext = self.get_filename_and_ext(name, mime_type=image.mime, assume_ext=".jpg")
        await self.handle_file(image.src, scrape_item, name, ext, custom_filename=filename)

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        album = await self.api.album(album_id)
        title = self.create_title(album.title, album_id)
        scrape_item.setup_as_album(title, album_id=album_id)

        async for images in self._album_images(album):
            for img in images:
                url = self.PRIMARY_URL / "img" / img.encoded_id
                new_item = scrape_item.create_child(url)
                await self._image(new_item, img)
                scrape_item.add_children()

    async def _album_images(self, album: Album) -> AsyncGenerator[Iterable[Image]]:
        already_downloaded = await self.get_album_results(album.encoded_id)

        def filter_images(images: Iterable[Image]):
            for img in images:
                if not self.check_album_results(img.src, already_downloaded):
                    yield img

        yield filter_images(album.images)
        if not album.has_more:
            return

        async for images in self.api.album_images(album.encoded_id, init_page=2):
            yield filter_images(images)


@dataclasses.dataclass(slots=True)
class Image:
    encoded_id: str
    mime: str
    created_at: str
    original_filename: str | None
    src: AbsoluteHttpURL

    @classmethod
    def parse(cls, img: dict[str, Any]) -> Self:
        return deserialize(cls, img, src=parse_url(img["original_url"], trim=False))


@dataclasses.dataclass(slots=True)
class Album:
    title: str
    description: str | None
    encoded_id: str
    images: tuple[Image, ...]
    has_more: bool


class GoonBoxAPI(API):
    async def image(self, image_id: str) -> Image:
        api_url = self.PRIMARY_URL / "api/images" / image_id
        resp = await self.request_json(api_url)
        return Image.parse(resp["image"])

    async def album(self, album_id: str) -> Album:
        api_url = self.PRIMARY_URL / "api/albums" / album_id
        resp = await self.request_json(api_url.with_query(per_page=100))
        return deserialize(
            Album,
            resp["album"],
            images=tuple(map(Image.parse, resp["images"])),
            has_more=resp["pagination"]["total"] > 1,
        )

    async def album_images(self, album_id: str, init_page: int = 1) -> AsyncGenerator[map[Image]]:
        api_url = self.PRIMARY_URL / "api/albums" / album_id / "images"
        for page in itertools.count(init_page):
            resp = await self.request_json(api_url.update_query(page=page, per_page=100))
            yield map(Image.parse, resp["images"])
            if page >= resp["pagination"]["last_page"]:
                break
