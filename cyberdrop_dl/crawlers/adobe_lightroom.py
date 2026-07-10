from __future__ import annotations

import dataclasses
import json
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import extr_text
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from cyberdrop_dl.url_objects import ScrapeItem


class AdobeLightroomCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Shared Album": "/shares/<space_id>",
    }
    DOMAIN: ClassVar[str] = "lightroom.adobe"
    FOLDER_DOMAIN: ClassVar[str] = "Adobe Lightroom"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://lightroom.adobe.com")

    def __post_init__(self) -> None:
        self.api: AdobeLightroomAPI = AdobeLightroomAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["shares", space_id]:
                return await self.album(scrape_item, space_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, space_id: str) -> None:
        album = await self.api.album(space_id)
        title = self.create_title(album.name, album.id)
        scrape_item.setup_as_album(title, album_id=album.id)

        async for images in self.api.images(album.assets_url):
            for image in images:
                self.create_eager_task(self._image(scrape_item.copy(), image, space_id))
                scrape_item.add_children()

    async def _image(self, scrape_item: ScrapeItem, image: Image, space_id: str) -> None:
        src = self.PRIMARY_URL / "v2c/spaces" / space_id / image.href
        with self.catch_errors(src):
            filename = self.create_custom_filename(image.id, ext := ".png")
            scrape_item.uploaded_at = self.parse_iso_date(image.created)
            await self.handle_file(src, scrape_item, image.id, ext, custom_filename=filename)


@dataclasses.dataclass(slots=True)
class Album:
    id: str
    name: str
    assets_url: AbsoluteHttpURL


@dataclasses.dataclass(slots=True)
class Image:
    id: str
    created: str
    size: int
    href: str


class AdobeLightroomAPI(API):
    async def album(self, space_id: str) -> Album:
        url = self.PRIMARY_URL / "shares" / space_id
        html = await self.request_text(url)
        try:
            attrs = extr_text(html, "albumAttributes: ", "};")
        except ValueError as e:
            raise ScrapeError(422, "Unable to extract album attributes") from e

        album = json.loads(attrs)
        try:
            name = album["payload"]["story"]["title"]
        except KeyError:
            name = album["payload"]["name"]

        assets_url = album["base"] + album["links"]["/rels/space_album_images_videos"]["href"]
        return Album(album["id"], name, self.parse_url(assets_url))

    async def images(self, assets_url: AbsoluteHttpURL) -> AsyncGenerator[map[Image]]:
        next_page = assets_url
        while True:
            content = await self.request_text(next_page)
            data = json.loads(content.removeprefix("while (1) {}\n"))
            yield map(_parse_image, data["resources"])
            try:
                next_href: str = data["links"]["next"]["href"]
            except KeyError:
                break
            if not next_href:
                break

            next_page = self.parse_url(data["base"] + next_href)


def _parse_image(resource: dict[str, Any]) -> Image:
    sizes = dict(_parse_links(resource["asset"]["links"]))
    max_size = max(sizes)
    return Image(
        id=resource["asset"]["id"],
        created=resource["asset"]["created"],
        size=max_size,
        href=sizes[max_size],
    )


def _parse_links(links: dict[str, dict[str, Any]]) -> Generator[tuple[int, str]]:
    for name, rendition in links.items():
        if rendition.get("templated") or not name.startswith("/rels/rendition_type/"):
            continue
        try:
            size = int(name.rpartition("/")[-1])
        except ValueError:
            continue

        yield size, rendition["href"]
