from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self

from cyberdrop_dl import aio
from cyberdrop_dl.cache import disk_cached_method
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import TextExtractor
from cyberdrop_dl.utils.dataclass import deserialize, struct
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.urls import parse_http_url

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from cyberdrop_dl.url_objects import ScrapeItem


class SmugMugCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Gallery": (
            "/gallery/n-<node-id>",
            "/gallery/<album-key>",
        ),
        "Photo": "/gallery/n-<node-id>/i-<image_key>",
    }

    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.smugmug.com")
    DOMAIN: ClassVar[str] = "smugmug"

    def __post_init__(self) -> None:
        self.api: SmugMugAPI = SmugMugAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["gallery", slug, *rest]:
                match rest:
                    case [image, *_] if image.startswith("i-"):
                        image_key = image.partition("-")[-1]
                    case _:
                        image_key = None

                match slug.partition("-"):
                    case ["n", _, node_id]:
                        await self.node(scrape_item, node_id, image_key)
                    case [album_key, "", ""]:
                        await self.album(scrape_item, album_key, image_key)
                    case _:
                        raise ValueError
            case _:
                raise ValueError

    @error_handling_wrapper
    async def node(self, scrape_item: ScrapeItem, node_id: str, image_key: str | None = None) -> None:
        node = await self.api.node(node_id)
        if node.Type != "Album":
            raise ScrapeError(422, f"Unsupported {node.Type = }")

        album_key = self.parse_url(node.Uris["Album"]).name
        await self.album(scrape_item, album_key, image_key)

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_key: str, image_key: str | None = None) -> None:
        album, downloaded = await aio.gather(self.api.album(album_key), self.get_completed_by_album(album_key))

        with scrape_item.track_changes:
            scrape_item.url = self.PRIMARY_URL / "gallery" / f"n-{album.NodeID}"

        scrape_item.setup_as_album(self.create_title(album.Name, album_key), album_id=album_key)

        if image_key:
            images = aio.to_async_iterable([await self.api.image(album_key, image_key)])
        else:
            images = self.api.album_images(album_key)

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg, aio.maybe_aclosing(images):
            tg.create_task(self.write_metadata(scrape_item, f"album_{album_key}", album))
            async for image in images:
                if image.src in downloaded:
                    continue
                new_item = scrape_item.create_child(image.web_url)
                tg.create_task(self._image(new_item, image))
                await sleep()

    @error_handling_wrapper
    async def _image(self, scrape_item: ScrapeItem, image: Image) -> None:
        scrape_item.uploaded_at = self.parse_iso_date(image.DateTimeUploaded)
        _, ext = self.get_filename_and_ext(image.FileName)
        await self.handle_file(
            image.src,
            scrape_item,
            image.FileName,
            ext,
            custom_filename=self.create_custom_filename(image.FileName, ext, file_id=image.ImageKey),
            thumbnail=image.thumb,
            metadata=image,
        )


@struct
class Node:
    DateAdded: str
    DateModified: str
    Description: str
    IsRoot: bool
    Name: str
    NodeID: str
    Type: Literal["Album", "Page", "Folder", "System Album", "System Page"]
    Uris: Mapping[str, str]


@struct
class Album:
    AlbumKey: str
    LastUpdated: str
    Name: str
    NodeID: str
    Title: str


@struct
class Image:
    src: AbsoluteHttpURL
    thumb: AbsoluteHttpURL
    web_url: AbsoluteHttpURL

    Caption: str
    Date: str
    DateTimeOriginal: str
    DateTimeUploaded: str
    FileName: str
    Hidden: bool
    ImageKey: str
    IsArchive: bool
    IsVideo: bool
    OriginalHeight: int
    OriginalSize: int
    OriginalWidth: int
    Title: str

    @classmethod
    def parse(cls, image: Mapping[str, str]) -> Self:
        return deserialize(
            cls,
            image,
            src=parse_http_url(image["ArchivedUri"]),
            thumb=parse_http_url(image["ThumbnailUrl"]),
            web_url=parse_http_url(image["WebUri"]),
        )


class SmugMugAPI(API):
    # https://api.smugmug.com/api/v2/doc/index.html
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.smugmug.com/api/v2")

    @disk_cached_method(ttl=86_400 * 15)
    async def api_key(self) -> str:
        html = await self.request_html(self.PRIMARY_URL)

        def parse(script: str):
            for line in script.split(","):
                name, _, value = line.partition(":")
                if value:
                    yield name.strip('"'), value.strip('"')

        for script in TextExtractor(html).repeat("window.config={", "snowplowConfig"):
            data = dict(parse(script))
            if data.get("api") == "https://api.smugmug.com" and (key := data.get("key")):
                return key

        return "W0g9oqdOrzuhEpIQ2qaTXimrzsfryKSZ"

    async def get(self, url: AbsoluteHttpURL) -> dict[str, Any]:
        resp = await self.request_json(
            url.update_query(APIKey=await self.api_key()),
            headers={"Accept": "application/json"},
        )
        return resp["Response"]

    async def node(self, node_id: str) -> Node:
        url = self.ENTRYPOINT / "node" / node_id
        resp = await self.get(url)
        node = resp["Node"]
        return deserialize(Node, node, Uris={k: v["Uri"] for k, v in node.get("Uris", {}).items()})

    async def image(self, album_key: str, image_key: str) -> Image:
        url = self.ENTRYPOINT / "album" / album_key / "image" / image_key
        resp = await self.get(url)
        return Image.parse(resp["AlbumImage"])

    async def album(self, album_key: str) -> Album:
        url = self.ENTRYPOINT / "album" / album_key
        resp = await self.get(url)
        return deserialize(Album, resp["Album"])

    async def album_images(self, album_key: str, *, count: int = 100) -> AsyncGenerator[Image]:
        previous_page: AbsoluteHttpURL | None = None
        current_page = (self.ENTRYPOINT / "album" / f"{album_key}!images").with_query(start=1, count=count)
        while previous_page != current_page:
            resp = await self.get(current_page)
            for image in resp["AlbumImage"]:
                yield Image.parse(image)

            previous_page = current_page
            if next_page := resp["Pages"].get("NextPage"):
                current_page = self.parse_url(next_page)
