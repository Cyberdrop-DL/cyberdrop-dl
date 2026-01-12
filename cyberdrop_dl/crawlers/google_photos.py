from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths, auto_task_id
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.utilities import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator

    from bs4 import BeautifulSoup

    from cyberdrop_dl.data_structures.url_objects import ScrapeItem


@dataclass(slots=True, frozen=True)
class Image:
    base_url: str
    width: int
    height: int
    display_id: str
    id: str
    date: int

    @staticmethod
    def parse(protobuf: list[Any]) -> Image:
        return Image(
            *protobuf[1][0:3],
            display_id=protobuf[0],
            date=protobuf[2] // 1000,
            id=protobuf[3],
        )


class GooglePhotosCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "photos.app.goo.gl", "photos.google.com"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Album": "/share/<album_id>",
        "Photo": "/album/<album_id>/photo/<photo_id>",
        "**NOTE**": "Only downloads 'optimized' images, NOT original quality",
        "**NOTE**2": "Can NOT download videos",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://photos.google.com")
    DOMAIN: ClassVar[str] = "photos.google"
    FOLDER_DOMAIN: ClassVar[str] = "GooglePhotos"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if scrape_item.url.host == "photos.app.goo.gl":
            return await self.follow_redirect(scrape_item)

        match scrape_item.url.parts[1:]:
            case ["album" | "share" as type_, album_id, "photo", photo_id, *_]:
                return await self.album(scrape_item, type_, album_id, photo_id)
            case ["album" | "share" as type_, album_id]:
                return await self.album(scrape_item, type_, album_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, type_: str, album_id: str, photo_id: str | None = None) -> None:
        album_url = (self.PRIMARY_URL / type_ / album_id).with_query(scrape_item.url.query)
        soup = await self.request_soup(album_url)
        album_name, images = _parse_album(soup)
        if album_name:
            title = self.create_title(album_name, album_id)
            scrape_item.setup_as_album(title, album_id=album_id)

        for idx, image in enumerate(images, 1):
            if photo_id and photo_id != image.display_id:
                continue

            web_url = self.PRIMARY_URL / type_ / album_id / "photo" / image.display_id
            new_scrape_item = scrape_item.create_child(web_url)
            self.create_task(self._image(new_scrape_item, image, idx))
            scrape_item.add_children()
            if photo_id:
                break

    @auto_task_id
    @error_handling_wrapper
    async def _image(self, scrape_item: ScrapeItem, image: Image, idx: int) -> None:
        link = self.parse_url(image.base_url + f"=w{image.width}-h{image.height}")
        scrape_item.possible_datetime = image.date

        async with self.request(link) as resp:
            ext = mimetypes.guess_extension(resp.content_type)

        assert ext
        filename, ext = self.get_filename_and_ext(image.id + ext)
        custom_filename = f"{str(idx).zfill(3)} - {filename}"
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            filename,
            ext,
            metadata=image,
            custom_filename=custom_filename,
            debrid_link=link,
        )


def _parse_album(soup: BeautifulSoup) -> tuple[str | None, Generator[Image]]:
    data = css.select_text(soup, "script[class='ds:1']:-soup-contains(AF_initDataCallback)")
    start, end = data.find("["), data.rfind("]") + 1
    protobuf: list[Any] = json.loads(data[start:end])
    name: str | None = protobuf[3][1] or None
    images = (Image.parse(img) for img in protobuf[1])
    return name, images
