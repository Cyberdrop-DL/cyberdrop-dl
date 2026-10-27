from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, override

from cyberdrop_dl.clients import etag
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


etag.register(
    etag.ETag(
        "68d194f7-3574",
        "You either don't have permission to access this image or it has been deleted",
        404,  # https://cdn.lensdump.com/404.png
    )
)


class LensDumpCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = ".l3n.co", "lensdump.com"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Image": ("/i/<image_id>",),
        "Direct Links": "https://<server>.l3n.co/.../<image_id>.<ext>",
    }
    DOMAIN: ClassVar[str] = "lensdump"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://lensdump.com")

    def __post_init__(self) -> None:
        self.update_cookies({"ld_nsfw_ok": "1"})
        self.api: LensDumpAPI = LensDumpAPI.from_crawler(self)

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case [*_, name] if url.host.endswith(".l3n.co"):
                image_id = name.partition(".")[0]
                return cls.PRIMARY_URL / "i" / image_id
            case _:
                return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["i", image_id]:
                await self.image(scrape_item, image_id)
            case ["404.png"]:
                await self.raise_exc(scrape_item, 404)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def image(self, scrape_item: ScrapeItem, image_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        image = await self.api.image(image_id)
        scrape_item.setup_as_album(self.create_title(image.album.name, image.album.id), album_id=image.album.id)
        await self._image(scrape_item, image)

    async def _image(self, scrape_item: ScrapeItem, image: Image) -> None:
        _, ext = self.get_filename_and_ext(image.filename)
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            image.title,
            ext,
            custom_filename=self.create_custom_filename(image.title, ext, file_id=image.id),
            metadata=image,
            debrid_link=self.parse_url(image.src),
            uploaded_at=int(self.parse_iso_date(image.uploaded_at)),
        )


@dataclasses.dataclass(slots=True, frozen=True)
class Image:
    id: str
    type: Literal["image"]
    title: str
    size: int
    uploaded_at: str
    album: Album
    filename: str
    src: str
    owner: Owner | None = None
    description: str | None = None

    @classmethod
    def parse(cls, image: dict[str, Any]) -> Self:
        return deserialize(
            cls,
            image,
            src=image["urls"]["file"],
            owner=deserialize(Owner, ow) if (ow := image.get("owner")) else None,
            album=deserialize(Album, image["album"]),
        )


@dataclasses.dataclass(slots=True, frozen=True)
class Owner:
    id: str
    username: str
    name: str


@dataclasses.dataclass(slots=True, frozen=True)
class Album:
    id: str
    name: str


class LensDumpAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://lensdump.com/api/2")

    async def image(self, image_id: str) -> Image:
        url = self.ENTRYPOINT / "files" / image_id
        resp = await self.request_json(url)
        return Image.parse(resp)
