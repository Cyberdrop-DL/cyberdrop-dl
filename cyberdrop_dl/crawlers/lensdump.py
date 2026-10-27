from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

from cyberdrop_dl import aio
from cyberdrop_dl.clients import etag
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedDomains, SupportedPaths
from cyberdrop_dl.exceptions import DownloadError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.url_objects import ScrapeItem

NOT_FOUND_MSG = "You either don't have permission to access this image or it has been deleted"

etag.register(
    etag.ETag(
        "686157ae6e2b3d52f9bf5fb8f531da42",
        NOT_FOUND_MSG,
        404,  # https://cdn.lensdump.com/404.png
    )
)


def _id(slug: str) -> str:
    return slug.partition(".")[0]


class LensDumpCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = ".l3n.co", "lensdump.com"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Image": "/i/<image_id>",
        "Album": "/a/<album_id>",
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
                return cls.PRIMARY_URL / "i" / _id(name)
            case ["i" | "a" as kind, name]:
                return cls.PRIMARY_URL / kind / _id(name)
            case _:
                return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["i", image_id]:
                await self.file(scrape_item, image_id)
            case ["a", album_id]:
                await self.album(scrape_item, album_id)
            case ["404.png"]:
                await self.raise_exc(scrape_item, 404)
            case [username] if username not in {"upload", "login", "pricing", "signup", "api"}:
                await self.user(scrape_item, username)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        album = await self.api.album(album_id)
        await self._album(scrape_item, album)

    def _album_title(self, album: Album) -> str:
        return self.create_title(album.name, album.id, force_album_id=album.name.lower() == "earlier uploads")

    @error_handling_wrapper
    async def _album(self, scrape_item: ScrapeItem, album: FullAlbum) -> None:
        scrape_item.setup_as_album(self._album_title(album), album_id=album.id)
        self.create_eager_task(self.write_metadata(scrape_item, f"album_{album.id}", album))
        if not album.files:
            raise ScrapeError(204, "Album has no files")

        if album.sub_albums:
            pass  # TODO: support this

        downloaded = await self.get_completed_by_album(album.id)
        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            async for image in self.api.album_files(album):
                web_url = self.PRIMARY_URL / "i" / image.id
                if web_url in downloaded:
                    continue
                tg.create_task(self._file(scrape_item.create_child(web_url), image))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def user(self, scrape_item: ScrapeItem, username: str) -> None:
        user = await self.api.user(username)
        scrape_item.setup_as_profile(self.create_title(f"{user.username} [user]"))
        self.create_eager_task(self.write_metadata(scrape_item, f"user_{user.username}", user))
        if not user.albums:
            raise ScrapeError(204, "User has no albums")

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            async for album in self.api.user_albums(user):
                web_url = self.PRIMARY_URL / "a" / album.id
                tg.create_task(self._album(scrape_item.create_child(web_url), album))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def file(self, scrape_item: ScrapeItem, image_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        image = await self.api.file(image_id)
        scrape_item.setup_as_album(self._album_title(image.album), album_id=image.album.id)
        await self._file(scrape_item, image)

    @error_handling_wrapper
    async def _file(self, scrape_item: ScrapeItem, file: File) -> None:
        src = self.parse_url(file.src)
        _, ext = self.get_filename_and_ext(src.name)
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            file.title,
            ext,
            custom_filename=self.create_custom_filename(file.title, ext, file_id=file.id),
            metadata=file,
            debrid_link=lambda: self.api.probe(src),
            uploaded_at=int(self.parse_iso_date(file.uploaded_at)),
        )


@dataclasses.dataclass(slots=True, frozen=True)
class File:
    id: str
    type: str
    title: str
    uploaded_at: str
    album: Album
    src: AbsoluteHttpURL | str
    owner: User | None = None
    description: str | None = None

    @classmethod
    def parse(cls, file: dict[str, Any], owner: User | None) -> Self:
        return deserialize(
            cls,
            file,
            src=file.get("src_url") or file["urls"]["file"],
            owner=owner,
            album=Album.parse(file["album"]),
            uploaded_at=file.get("uploaded_at") or file["date"],
        )


@dataclasses.dataclass(slots=True, frozen=True)
class User:
    id: str
    username: str
    name: str | None

    parse = classmethod(deserialize)


@dataclasses.dataclass(slots=True, frozen=True)
class FullUser(User):
    files: int
    albums: int
    bio: str | None
    tier: str


@dataclasses.dataclass(slots=True, frozen=True)
class Album:
    id: str
    name: str

    parse = classmethod(deserialize)


@dataclasses.dataclass(slots=True, frozen=True)
class FullAlbum(Album):
    files: int
    sub_albums: int
    owner: User | None
    created_at: str | None = None
    parent: str | None = None


class LensDumpAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://lensdump.com/api/2")

    async def file(self, image_id: str) -> File:
        url = self.ENTRYPOINT / "files" / image_id
        resp = await self.request_json(url)
        owner = resp.get("owner")
        return File.parse(resp, owner=User.parse(owner) if owner else None)

    async def probe(self, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        async with self.request(url) as resp:
            if resp.url.name == "404.png":
                raise DownloadError(404, NOT_FOUND_MSG)
            return resp.url

    async def user(self, username: str) -> FullUser:
        url = self.ENTRYPOINT / "users" / username
        resp = await self.request_json(url)
        return FullUser.parse(resp)

    async def album(self, album_id: str) -> FullAlbum:
        url = self.ENTRYPOINT / "albums" / album_id
        resp = await self.request_json(url)
        owner = resp.get("owner")
        return FullAlbum.parse(resp, owner=User.parse(owner) if owner else None)

    async def user_albums(self, user: User) -> AsyncGenerator[FullAlbum]:
        url = self.ENTRYPOINT / "users" / user.username / "albums"
        async for album in self._pager(url):
            yield FullAlbum.parse(album, owner=user)

    async def album_files(self, album: FullAlbum) -> AsyncGenerator[File]:
        url = self.ENTRYPOINT / "albums" / album.id / "files"
        async for file in self._pager(url):
            file["src_url"] = _thumb_to_src(self.parse_url(file["preview"]))
            yield File.parse(file, album.owner)

    async def _pager(self, url: AbsoluteHttpURL) -> AsyncGenerator[dict[str, Any]]:
        while True:
            resp = await self.request_json(url)
            for item in resp["items"]:
                yield item

            cursor = resp.get("next_cursor")
            if not cursor:
                break

            url = url.update_query(cursor=cursor)


def _thumb_to_src(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    return url.with_name(url.name.replace(".th.", ".").replace(".md.", "."))
