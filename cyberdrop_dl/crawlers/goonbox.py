from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, Self

from cyberdrop_dl.crawlers import Registry
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import parse_url
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from cyberdrop_dl.url_objects import ScrapeItem

_CDN = "cuckcapital.cr"


@Registry.database.fix_referer
class GoonBoxCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "selti-delivery.ru", "goonbox", _CDN
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Image": "/img/<image_id>",
        "Album": "/a/<album_id>",
        "User albums": "/u/<username>",
        "User images": (
            "/u/<username>/images",
            "/u/<username>?tab=images",
        ),
        "Direct links": "",
    }

    DOMAIN: ClassVar[str] = "goonbox"
    FOLDER_DOMAIN: ClassVar[str] = "GoonBox"
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = (
        "host.church",
        "jpg.homes",
        "jpg.church",
        "jpg.fish",
        "jpg.fishing",
        "jpg.pet",
        "jpeg.pet",
        "jpg1.su",
        "jpg2.su",
        "jpg3.su",
        "jpg4.su",
        "jpg5.su",
        "jpg6.su",
        "jpg7.cr",
    )
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://goonbox.cr")

    def __post_init__(self) -> None:
        self.api: GoonBoxAPI = GoonBoxAPI.from_crawler(self)

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        if cls.is_subdomain(url):
            return _fix_cdn(_thumb_to_src(url))

        match url.parts[1:]:
            case ["a" | "img" as part, slug, *_]:
                return (url.origin() / part / _id(slug)).with_query(url.query)
            case _:
                return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if self.is_subdomain(scrape_item.url):
            await self.direct_file(scrape_item)
            return

        match scrape_item.url.parts[1:]:
            case ["img", file_id]:
                await self.image(scrape_item, file_id)
            case ["a", album_id]:
                await self.album(scrape_item, album_id)
            case ["u", user, "images"]:
                await self.user_images(scrape_item, user)
            case ["u", user]:
                if scrape_item.url.query.get("tab") == "images":
                    await self.user_images(scrape_item, user)
                else:
                    await self.user_albums(scrape_item, user)
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
        await self._album(scrape_item, album)

    @error_handling_wrapper
    async def user_albums(self, scrape_item: ScrapeItem, user: str) -> None:
        scrape_item.setup_as_profile(self.create_title(f"{user} [user]"))

        async for albums in self.api.user_albums(user, scrape_item.url.query):
            async with self.new_task_group() as tg:
                for album in albums:
                    url = self.PRIMARY_URL / "a" / album.encoded_id
                    new_item = scrape_item.create_child(url)
                    tg.create_lazy_task(self._album(new_item, album))
                    scrape_item.add_children()

    @error_handling_wrapper
    async def user_images(self, scrape_item: ScrapeItem, user: str) -> None:
        scrape_item.setup_as_profile(self.create_title(f"{user} [user]"))
        scrape_item.append_folders("images")

        async for images in self.api.user_images(user, scrape_item.url.query):
            for img in images:
                url = self.PRIMARY_URL / "img" / img.encoded_id
                new_item = scrape_item.create_child(url)
                self.create_eager_task(self._image(new_item, img))
                scrape_item.add_children()

    @error_handling_wrapper
    async def _album(self, scrape_item: ScrapeItem, album: Album) -> None:
        title = self.create_title(album.title, album.encoded_id)
        scrape_item.setup_as_album(title, album_id=album.encoded_id)

        downloaded = await self.get_completed_by_album(album.encoded_id)

        async for images in self.api.album_images(album.encoded_id, scrape_item.url.query):
            for img in images:
                if img.src in downloaded:
                    continue

                url = self.PRIMARY_URL / "img" / img.encoded_id
                new_item = scrape_item.create_child(url)
                self.create_eager_task(self._image(new_item, img))
                scrape_item.add_children()


@dataclasses.dataclass(frozen=True, slots=True)
class Image:
    encoded_id: str
    mime: str
    created_at: str
    original_filename: str | None
    src: AbsoluteHttpURL

    @classmethod
    def parse(cls, img: dict[str, Any]) -> Self:
        return deserialize(cls, img, src=parse_url(img["original_url"]))


@dataclasses.dataclass(frozen=True, slots=True)
class Album:
    title: str
    description: str | None
    encoded_id: str

    parse = classmethod(deserialize)


class GoonBoxAPI(API):
    async def image(self, image_id: str) -> Image:
        api_url = self.PRIMARY_URL / "api/images" / image_id
        resp = await self.request_json(api_url)
        return Image.parse(resp["image"])

    async def album(self, album_id: str) -> Album:
        api_url = self.PRIMARY_URL / "api/albums" / album_id
        resp = await self.request_json(api_url)
        return Album.parse(resp["album"])

    async def album_images(self, album_id: str, query: Mapping[str, Any]) -> AsyncGenerator[map[Image]]:
        api_url = self.PRIMARY_URL / "api/albums" / album_id / "images"
        async for page in self._pager(api_url, "images", query):
            yield map(Image.parse, page)

    async def user_albums(self, user: str, query: Mapping[str, Any]) -> AsyncGenerator[map[Album]]:
        api_url = self.PRIMARY_URL / "api/users" / user / "albums"
        async for page in self._pager(api_url, "albums", query):
            yield map(Album.parse, page)

    async def user_images(self, user: str, query: Mapping[str, Any]) -> AsyncGenerator[map[Image]]:
        api_url = self.PRIMARY_URL / "api/users" / user / "images"
        async for page in self._pager(api_url, "images", query):
            yield map(Image.parse, page)

    async def _pager(
        self, url: AbsoluteHttpURL, key: str, query: Mapping[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]]]:
        url = url.update_query(_filter_query(query))
        while True:
            resp = await self.request_json(url)
            yield resp[key]
            current_page: int = resp["pagination"]["current_page"]
            if current_page >= resp["pagination"]["last_page"]:
                break
            url = url.update_query(page=current_page + 1)


def _filter_query(query: Mapping[str, str]) -> dict[str, str | int]:
    sort = query.get("sort")
    return {
        "page": int(query.get("page") or 1),
        "per_page": 100,
        "sort": sort if sort in {"newest", "oldest", "most_images", "least_images"} else "newest",
    }


def _fix_cdn(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    if GoonBoxCrawler.is_subdomain(url) and not url.host.endswith(_CDN):
        server, *_ = url.host.rsplit(".", 2)
        return url.with_host(f"{server}.{_CDN}")
    return url


def _id(slug: str) -> str:
    return slug.rsplit(".", maxsplit=1)[-1]


def _thumb_to_src(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    new_name = url.name
    for trash in (".md.", ".th.", ".fr."):
        new_name = new_name.replace(trash, ".", 1)
    return url.with_name(new_name)
