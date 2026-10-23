from __future__ import annotations

import base64
import contextlib
import dataclasses
import re
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, ClassVar, Final, Literal, Self, Unpack, override

from cyberdrop_dl import aio
from cyberdrop_dl.cache import disk_cached_method
from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedDomains, SupportedPaths, URLConfig, auto_task_id
from cyberdrop_dl.exceptions import DDOSGuardError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import b64_pad, css
from cyberdrop_dl.utils._url import remove_query_params
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable, Generator, Iterable

    from cyberdrop_dl.clients.request import RequestParams
    from cyberdrop_dl.clients.response import AbstractResponse
    from cyberdrop_dl.constants import HttpMethod
    from cyberdrop_dl.url_objects import ScrapeItem


@Crawler.db_path_builder("path_qs")
class VKBaseCrawler(Crawler, is_abc=True):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/clip<owner_id>_<video_id>",
            "/video<owner_id>_<video_id>?list=<access_key>",
            "/video_ext.php?oid=<owner_id>&id=<video_id>",
        ),
    }
    DOMAIN: ClassVar[str] = "vk"
    FOLDER_DOMAIN: ClassVar[str] = "VK"

    def __post_init__(self) -> None:
        for host in self.SUPPORTED_DOMAINS:
            self.update_cookies(
                {"remixlang": 3, "remixage18": 1},
                self.PRIMARY_URL.with_host(host),
            )
        self.api: VKAPI = VKAPI.instance or VKAPI.from_crawler(self)

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url).without_query_params("pl")  # TODO: support playlists
        match url.parts[1:]:
            case ["video_ext.php"] if (owner_id := url.query.get("oid")) and (vid := url.query.get("id")):
                return VKVideoCrawler.PRIMARY_URL / f"video{owner_id}_{vid}"
            case [slug]:
                if slug.startswith("@") and "vkvideo" in url.host:
                    return url / "all"
                if slug.startswith(("video", "clip")):
                    return url.with_host(VKVideoCrawler.PRIMARY_URL.host)
                return url
            case _:
                return url


class VKVideoCrawler(VKBaseCrawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = VKBaseCrawler.SUPPORTED_PATHS | {
        "User / Group videos": (
            "@<owner_screen_name>",
            "@<owner_screen_name>/clips",
            "@<owner_screen_name>/all",
            "@<owner_screen_name>/donut",
        ),
    }
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "vkvideo.ru", "vkvideo.com"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vkvideo.com")

    @staticmethod
    @override
    def __db_path__(url: AbsoluteHttpURL, /) -> str:
        url = url.without_query_params("tkn")
        if url.parts[1].startswith(("video", "clip")):
            url = remove_query_params(url, keep=("list",))
        return url.path_qs

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [owner, "clips" | "all" | "donut" as kind]:
                kind = "videos" if kind == "all" else kind
                await self.owner_videos(scrape_item, owner.removeprefix("@"), kind)
            case [slug] if video := _extract_id(slug, "clip", "video", composed=True):
                owner_id, _, video_id = video.partition("_")
                await self.video(scrape_item, owner_id, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def owner_videos(self, scrape_item: ScrapeItem, owner_id: str, kind: str) -> None:
        owner = await self.api.resolve_owner(owner_id)
        scrape_item.setup_as_profile(self.create_title(owner.full_name))
        scrape_item.append_folders(kind)
        async with self.new_task_group() as tg:
            async for video in self.api.get_videos(scrape_item.url):
                prefix = "clip" if video.type == "short_video" else "video"
                url = self.PRIMARY_URL / f"{prefix}{video.owner_id}_{video.id}"
                if video.access_key:
                    url = url.update_query(list=video.access_key)
                tg.create_task(self.video_task(scrape_item.create_child(url), video))
                scrape_item.add_children()

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, owner_id: str, video_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        video = await self.api.get_video(owner_id, video_id, access_key=scrape_item.url.query.get("list"))
        await self._video(scrape_item, video)

    @error_handling_wrapper
    async def video_task(self, scrape_item: ScrapeItem, video: Video) -> None:
        if await self.check_complete(scrape_item.url):
            return

        await self._video(scrape_item, video)

    async def _video(self, scrape_item: ScrapeItem, video: Video) -> None:
        scrape_item.uploaded_at = video.date
        if video.embed:
            new_item = scrape_item.create_child(self.parse_url(video.embed))
            new_item.setup_as_album(self.create_title(video.title))
            self.handle_embed(new_item)
            return

        best_fmt = max(video.formats, key=lambda f: f.score)
        m3u8 = info = debrid_url = None
        if best_fmt.hls:
            m3u8, info = await self.request_m3u8(best_fmt.url)
        else:
            debrid_url = best_fmt.url

        await self.handle_file(
            scrape_item.url,
            scrape_item,
            video.title,
            ext := ".mp4",
            m3u8=m3u8,
            custom_filename=self.create_custom_filename(
                video.title,
                ext,
                file_id=f"{video.owner_id}_{video.id}",
                resolution=info.resolution if info else best_fmt.height,
            ),
            thumbnail=video.thumb,
            debrid_link=debrid_url,
            metadata=video,
        )


@URLConfig(allow_empty_path=True)
class VKCrawler(VKBaseCrawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "vk.ru", "vk.com"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = VKBaseCrawler.SUPPORTED_PATHS | {
        "User / Group wall": (
            "/id<owner_id>",
            "/public<owner_id>",
            "/@<owner_screen_name>",
            "/album<owner_id>_00",
        ),
        "User / Group photos": (
            "/albums<owner_id>",
            "/photos<owner_id>",
        ),
        "User / Group clips": (
            "/id<owner_id>#section=short_videos",
            "/public<owner_id>#section=short_videos",
            "/@<owner_screen_name>#section=short_videos",
        ),
        "User / Group videos": (
            "/id<owner_id>#section=videos",
            "/public<owner_id>#section=videos",
            "/@<owner_screen_name>#section=videos",
        ),
        "Album": "/album<owner_id>_<album_id>",
        "Post": "/wall<owner_id>_<wall_id>",
        "Redirect": "/?to=<base64_url>",
    }

    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vk.com")

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        if "vkvideo" in scrape_item.url.host:
            self.handle_external_links(scrape_item)
            return

        await self._fetch(scrape_item)

    async def _fetch(self, scrape_item: ScrapeItem) -> None:
        url = scrape_item.url
        match url.parts[1:]:
            case [] if redirect := url.query.get("to"):
                self.redirect(scrape_item, redirect)
            case [slug]:
                if owner_id := _extract_id(slug, "id", "@"):
                    await self.wall(scrape_item, owner_id)
                elif owner_id := _extract_id(slug, "public"):
                    await self.wall(scrape_item, f"-{owner_id}")
                elif album := _extract_id(slug, "album", composed=True):
                    owner_id, _, album_id = album.partition("_")
                    if album_id == "00":
                        await self.wall(scrape_item, owner_id)
                    else:
                        await self.album(scrape_item, owner_id, album_id)
                elif owner_id := _extract_id(slug, "albums", "photos"):
                    await self.photos(scrape_item, owner_id)
                elif wall := _extract_id(slug, "wall", composed=True):
                    owner_id, _, post_id = wall.partition("_")
                    await self.post(scrape_item, owner_id, post_id)
                elif photo := _extract_id(slug, "photo", composed=True):
                    owner_id, _, photo_id = photo.partition("_")
                    await self.photo(scrape_item, owner_id, photo_id)
                else:
                    raise ValueError
            case _:
                raise ValueError

    @error_handling_wrapper
    def redirect(self, scrape_item: ScrapeItem, to: str) -> None:
        url = base64.urlsafe_b64decode(b64_pad(to)).decode("utf8")
        self.handle_external_links(scrape_item.create_child(self.parse_url(url)))

    @error_handling_wrapper
    async def photos(self, scrape_item: ScrapeItem, owner_id: str) -> None:
        raise NotImplementedError

    @error_handling_wrapper
    async def photo(self, scrape_item: ScrapeItem, owner_id: str, photo_id: str) -> None:
        owner = await self.api.resolve_owner(owner_id)
        scrape_item.setup_as_profile(self.create_title(owner.full_name))
        post = await self.api.get_post(owner_id, photo_id)
        await self._post(scrape_item, post)

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, owner_id: str, album_id: str) -> None:
        owner = await self.api.resolve_owner(owner_id)
        scrape_item.setup_as_profile(self.create_title(owner.full_name))
        scrape_item.append_folders(f"album_{album_id}")
        await self._iter_photos_legacy(scrape_item, f"album{owner_id}_{album_id}")

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, owner_id: str, post_id: str) -> None:
        owner = await self.api.resolve_owner(owner_id)
        scrape_item.setup_as_profile(self.create_title(owner.full_name))
        post = await self.api.get_post(owner_id, post_id)
        await self._post(scrape_item, post)

    @error_handling_wrapper
    async def wall(self, scrape_item: ScrapeItem, owner_id: str) -> None:
        owner = await self.api.resolve_owner(owner_id)
        domain = str(
            f"@{owner.screen_name}" if owner.screen_name else 0 - owner.id if owner.type == "page" else owner.id
        )
        match scrape_item.url.fragment.partition("="):
            case ["section", _, "short_videos"]:
                url = VKVideoCrawler.PRIMARY_URL / domain / "all"
            case ["section", _, "videos"]:
                url = VKVideoCrawler.PRIMARY_URL / domain / "clips"
            case _:
                url = None

        if url:
            with scrape_item.track_changes:
                scrape_item.url = url
                self.handle_external_links(scrape_item)
                return

        scrape_item.setup_as_profile(self.create_title(owner.full_name))
        async with self.new_task_group() as tg:
            async for post in self.api.get_wall(owner_id):
                url = self.PRIMARY_URL / f"wall{post.owner_id}_{post.id}"
                tg.create_task(self._post_task(scrape_item.create_child(url), post))
                scrape_item.add_children()

    @error_handling_wrapper
    async def _post(self, scrape_item: ScrapeItem, post: Post) -> None:
        title = self.create_separate_post_title(None, str(post.id), post.date)
        scrape_item.setup_as_post(title)
        async with self.new_task_group() as tg:
            tg.create_task(self.write_metadata(scrape_item, f"wall{post.owner_id}_{post.id}", post))
            for attach in post.attachments:
                match attach["type"]:
                    case "photo":
                        photo = _parse_photo(attach["photo"])
                        url = self.PRIMARY_URL / photo.web_path
                        tg.create_task(self._photo(scrape_item.create_child(url), photo))

                    case "video":
                        vid = await _parse_video(attach["video"])
                        url = VKVideoCrawler.PRIMARY_URL / vid.web_path
                        self.handle_external_links(scrape_item.create_child(url))

                    case "audio":
                        _audio = Audio.parse(attach["audio"])

                    case "doc":
                        _file = File.parse(attach["doc"])

                    case "graffiti":
                        _file = Graffiti.parse(attach["graffiti"])

                    case "link":
                        _link = Link.parse(attach["link"])

                    case "album":
                        _link = Album.parse(attach["album"])

                    case "app" | "pool" | "page" | "market" | "market_album" | "sticker":
                        continue

                    case _:  # TODO: support 'pretty_cards' and 'event'
                        self.log.warning("Unknown attachment type: %s", attach)
                        continue

                scrape_item.add_children()

    _post_task = auto_task_id(_post)

    @error_handling_wrapper
    async def _photo(self, scrape_item: ScrapeItem, photo: Photo) -> None:
        best = max(photo.sources, key=lambda s: s.score)
        _, ext = self.get_filename_and_ext(best.url.name, assume_ext=".jpg")
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            best.url.name,
            ext,
            custom_filename=self.create_custom_filename(photo.web_path, ext, video_codec=best.type),
            metadata=photo,
            debrid_link=best.url,
            uploaded_at=photo.date,
        )

    _photo_task = auto_task_id(_photo)

    async def _iter_photos_legacy(self, scrape_item: ScrapeItem, list_id: str) -> None:
        async with self.new_task_group() as tg:
            async for photo in self.api.legacy.get_photos(list_id):
                new_item = scrape_item.create_child(self.PRIMARY_URL / photo.web_path)
                tg.create_task(self._photo_task(new_item, photo))
                scrape_item.add_children()


@dataclasses.dataclass(slots=True, frozen=True)
class Object:
    parse = classmethod(deserialize)


@dataclasses.dataclass(slots=True, frozen=True)
class Post(Object):
    date: int
    id: int
    from_id: int
    owner_id: int
    attachments: list[dict[str, Any]]
    text: str | None = None


@dataclasses.dataclass(slots=True, frozen=True)
class Owner(Object):
    id: int
    type: str
    screen_name: str | None = None
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None

    @property
    def full_name(self) -> str:
        return (
            " ".join(filter(None, (self.first_name, self.last_name))) or self.name or self.screen_name or str(self.id)
        )


@dataclasses.dataclass(slots=True, frozen=True)
class Format(Object):
    name: str
    url: AbsoluteHttpURL
    height: int | None = None
    hls: bool = False

    @property
    def score(self) -> tuple[bool, int]:
        return (not self.hls, self.height or 0)


@dataclasses.dataclass(slots=True, frozen=True)
class Video(Object):
    id: int
    owner_id: int
    title: str
    thumb: str | None
    date: int
    embed: str | None
    formats: tuple[Format, ...]
    type: str = "video"
    access_key: str | None = None

    @property
    def slug(self) -> str:
        return f"{self.owner_id}_{self.id}"

    @property
    def prefix(self) -> str:
        return "clip" if self.type == "short_video" else "video"

    @property
    def web_path(self) -> str:
        return f"{self.prefix}{self.slug}"


@dataclasses.dataclass(slots=True, frozen=True)
class PhotoSize(Object):
    TYPES: ClassVar[tuple[str, ...]] = (
        "base",
        "s",
        "m",
        "o",
        "p",
        "q",
        "r",
        "x",
        "y",
        "z",
        "w",
        "orig",
    )  # worst to best
    type: str
    url: AbsoluteHttpURL
    height: int | None = None
    width: int | None = None

    @property
    def score(self) -> int:
        try:
            return self.TYPES.index(self.type)
        except ValueError:
            raise ScrapeError(422, f"Unknown size for {self}") from None


@dataclasses.dataclass(slots=True, frozen=True)
class Photo(Object):
    id: int
    owner_id: int
    date: int
    sources: tuple[PhotoSize, ...]

    @property
    def slug(self) -> str:
        return f"{self.owner_id}_{self.id}"

    @property
    def web_path(self) -> str:
        return f"photo{self.slug}"


@dataclasses.dataclass(slots=True, frozen=True)
class Audio(Object):
    id: int
    owner_id: int
    artist: str
    title: str
    url: str
    date: int
    album_id: int | None = None


@dataclasses.dataclass(slots=True, frozen=True)
class Graffiti(Object):
    id: int
    owner_id: int
    photo_130: str
    photo_604: str


@dataclasses.dataclass(slots=True, frozen=True)
class File(Object):
    id: int
    owner_id: int
    title: str
    ext: str
    url: str
    date: int


@dataclasses.dataclass(slots=True, frozen=True)
class Link(Object):
    url: str
    title: str
    description: str
    caption: str | None = None


@dataclasses.dataclass(slots=True, frozen=True)
class Album(Object):
    id: int
    owner_id: int
    title: str
    created: int
    size: int


@dataclasses.dataclass(slots=True, frozen=True)
class CatalogSection(Object):
    id: str
    next_from: str | None
    videos: list[dict[str, Any]]


ERROR_CODES: Final = (
    dict.fromkeys((30, 200, 201, 202, 203), HTTPStatus.FORBIDDEN)
    | dict.fromkeys((6, 9, 17, 18, 29), HTTPStatus.TOO_MANY_REQUESTS)
    | dict.fromkeys((1, 10), HTTPStatus.INTERNAL_SERVER_ERROR)
    | dict.fromkeys((5, 7), HTTPStatus.UNAUTHORIZED)
)


@HTTPConfig(rate_limit=(2, 1))
class VKAPI(API):
    # https://dev.vk.ru/en/reference
    APP_ID: ClassVar[str] = "6287487"
    VERSION: ClassVar[str] = "5.289"
    CLIENT_ID: ClassVar[str] = "6287487"
    VIDEO_ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.vkvideo.ru")
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://web.api.vk.ru")
    instance: Self | None = None

    def __post_init__(self) -> None:
        self._owners: dict[str | int, Owner] = {}
        self._owners_locks: aio.WeakAsyncLocks[str | int] = aio.WeakAsyncLocks()
        self.legacy: VKLegacyAPI = VKLegacyAPI(self)
        self.instance = self

    @override
    @contextlib.asynccontextmanager
    async def request(
        self, url: AbsoluteHttpURL, /, method: HttpMethod = "GET", **kwargs: Unpack[RequestParams]
    ) -> AsyncGenerator[AbstractResponse[Any]]:
        async with super().request(url, method, **kwargs) as resp:
            if resp.url.name == "challenge.html":
                raise DDOSGuardError(f"JS challenge from VK: {resp.url}")

            yield resp

    @disk_cached_method(ttl=3600)
    async def access_token(self) -> str:
        resp = await self.request_json(
            AbsoluteHttpURL("https://login.vk.ru/?act=get_anonym_token"),
            "POST",
            data={
                "app_id": self.APP_ID,
                "version": 1,
                "client_id": self.CLIENT_ID,
                "isApiOauthAnonymEnabled": "false",
                "scopes": "audio_anonymous,video_anonymous,photos_anonymous,profile_anonymous",
            },
        )
        if resp.get("type") != "okay":
            raise ScrapeError(401, str(resp))

        return resp["data"]["access_token"]

    async def method(self, method: str, data: dict[str, Any]) -> Any:
        data["access_token"] = await self.access_token()
        url = (self.ENTRYPOINT / "method" / method).with_query(v=self.VERSION, client_id=self.CLIENT_ID)
        resp = await self.request_json(url, "POST", data=data)
        if error := resp.get("error"):
            http_code = ERROR_CODES.get(ecode := error.get("error_code"), HTTPStatus.FORBIDDEN)
            if ecode == 3:
                self.access_token.clear()
            raise ScrapeError(http_code, error.get("error_msg"))

        return resp["response"]

    async def get_user(self, screen_name_or_id: str | int) -> Owner:
        resp = await self.method("users.get", {"user_ids": str(screen_name_or_id)})
        if not resp:
            raise ScrapeError(404, f"User not found: {screen_name_or_id}")
        return deserialize(Owner, resp[0], type="user")

    async def get_group(self, group_id: str | int) -> Owner:
        resp = await self.method("groups.getById", {"group_ids": str(group_id).lstrip("-")})
        groups = resp.get("groups")
        if not groups:
            raise ScrapeError(404, f"Group not found: {group_id}")
        return deserialize(Owner, groups[0])

    async def get_post(self, owner_id: str, post_id: str) -> Post:
        resp = await self.method("wall.getById", {"posts": f"{owner_id}_{post_id}"})
        items = resp.get("items")
        if not items:
            raise ScrapeError(404)
        return Post.parse(items[0])

    async def resolve_owner(self, screen_name: str) -> Owner:
        try:
            owner_id = int(screen_name)
        except ValueError:
            return await self._cached_owner(screen_name, self.owner_by_screen_name)
        else:
            return await self._cached_owner(owner_id, self.owner_by_id)

    async def _cached_owner(self, screen_name_or_id: str | int, fn: Callable[..., Awaitable[Owner]]) -> Owner:
        with contextlib.suppress(LookupError):
            return self._owners[screen_name_or_id]

        async with self._owners_locks[screen_name_or_id]:
            with contextlib.suppress(LookupError):
                return self._owners[screen_name_or_id]

            owner = await fn(screen_name_or_id)
            for key in {owner.id, screen_name_or_id}:
                self._owners[key] = owner
            return owner

    async def owner_by_id(self, owner_id: str | int) -> Owner:
        owner_id = int(owner_id)
        errors: list[Exception] = []
        for method in (self.get_user, self.get_group):
            try:
                return await method(owner_id)
            except ScrapeError as e:
                errors.append(e)

        raise BaseExceptionGroup(f"Unable to resolve {owner_id = }", tuple(errors))

    async def owner_by_screen_name(self, screen_name: str) -> Owner:
        owner = await self.method("utils.resolveScreenName", {"screen_name": screen_name.removeprefix("@")})
        owner_id, owner_type = owner["object_id"], owner["type"]
        match owner_type:
            case "group":
                resolve = self.get_group
            case "user":
                resolve = self.get_user
            case _:
                raise ScrapeError(422, f"Unsupported owner type: {owner}")

        return await resolve(owner_id)

    async def get_wall(
        self,
        domain: str,
        *,
        count: int = 20,
        offset: int = 0,
        filter_: Literal["all", "others", "owner"] = "all",
    ) -> AsyncGenerator[Post]:
        data = {
            "domain": domain,
            "count": count,
            "filter": filter_,
            "offset": offset or "",
        }

        seen: set[int] = set()
        resp = await self.method("wall.get", data)
        total = resp["count"]
        while True:
            offset += len(posts := resp["items"])
            found_new_posts: bool = False
            for post in map(Post.parse, posts):
                if post.id not in seen:
                    seen.add(post.id)
                    found_new_posts = True
                    yield post

            if not found_new_posts or offset >= total:
                break

            data["offset"] = offset

    async def get_catalog_video(self, url: AbsoluteHttpURL) -> CatalogSection:
        resp = await self.method(
            "catalog.getVideo",
            {
                "url": str(url),
                "ref": "",
                "from_trackcode": "",
                "need_blocks": "1",
                "applied_toggles": "[]",
                "enabled_features": "[]",
            },
        )
        catalog = resp["catalog"]
        section_id = catalog["default_section"]
        section = next(s for s in catalog["sections"] if s["id"] == section_id)
        return CatalogSection(section_id, next_from=section.get("next_from"), videos=resp["videos"])

    async def get_catalog_section(self, section_id: str, start_from: str) -> CatalogSection:
        resp = await self.method(
            "catalog.getSection",
            {
                "section_id": section_id,
                "start_from": start_from,
                "from_trackcode": "",
                "enabled_features": "[]",
            },
        )
        next_from = resp["section"]["next_from"]
        return CatalogSection(section_id, next_from, resp["videos"])

    async def get_videos(self, url: AbsoluteHttpURL, *, count: int = 20) -> AsyncGenerator[Video]:
        section = await self.get_catalog_video(url)
        seen: set[str] = set()
        while True:
            found_new_videos: bool = False
            for vid in section.videos:
                video = await _parse_video(vid)
                if video.slug not in seen:
                    seen.add(video.slug)
                    found_new_videos = True
                    yield video

            if not found_new_videos or len(section.videos) < count or not section.next_from:
                break

            section = await self.get_catalog_section(section.id, section.next_from)

    async def get_video(self, owner_id: str, video_id: str, *, access_key: str | None = None) -> Video:
        # Access key is for private videos
        full_id = f"{owner_id}_{video_id}"
        if access_key:
            full_id += f"_{access_key}"
        data = {"videos": full_id}

        resp = await self.method("video.get", data)
        items = resp.get("items")
        if not items:
            raise ScrapeError(404)
        return await _parse_video(items[0])


class VKLegacyAPI(API.Endpoint[VKAPI]):
    async def _payload(self, path: str, data: dict[str, Any]) -> list[Any]:
        resp = await self.api.request_json(
            url := VKCrawler.PRIMARY_URL / path,
            data=data,
            impersonate=True,
            headers={
                "Referer": str(url),
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        code, payload = resp["payload"]
        match code:
            case "8":
                raise ScrapeError(403, payload[0].strip('"'))
            case "3":
                raise ScrapeError(401)
            case _:
                return payload

    async def get_video(self, owner_id: str, video_id: str, *, access_key: str | None = None) -> Video:
        # This may trigger a JS bot check
        data = {
            "act": "show",
            "video": f"{owner_id}-{video_id}",
            "al": 1,
        }
        if access_key:
            data["list"] = access_key

        payload = await self._payload("al_video.php", data)
        return await _parse_video_legacy(payload, owner_id, video_id)

    async def get_photos(self, list_id: str, *, offset: int = 0) -> AsyncGenerator[Photo]:
        data = {
            "act": "show",
            "al": "1",
            "direction": "1",
            "list": list_id,
            "offset": offset,
        }

        seen: set[int] = set()
        while True:
            payload = await self._payload("al_photos.php", data)
            total, photos = payload[1], payload[3]
            offset += len(photos)
            found_new_photos: bool = False
            for photo in map(_parse_photo_legacy, photos):
                if photo.id not in seen:
                    seen.add(photo.id)
                    found_new_photos = True
                    yield photo

            if not found_new_photos or offset >= total:
                break

            data["offset"] = offset


def _extract_id(slug: str, *prefixes: str, composed: bool = False) -> str | None:
    for prefix in prefixes:
        if slug.startswith(prefix):
            target = slug.removeprefix(prefix)
            if composed != ("_" in target):
                raise ValueError(target)
            return target


@aio.to_thread
def _parse_video_legacy(payload: list[Any], owner_id: str, video_id: str) -> Video:
    html, options = payload[1], payload[-1]
    params = options["player"]["params"][0]
    if params.get("live") == 2:
        raise ScrapeError(422, "Live streams are not supported")

    def extract_embed() -> str | None:
        try:
            return css.select(css.soup(html), "iframe[src]", "src")
        except css.SelectorError:
            return None

    return Video(
        id=int(video_id),
        owner_id=int(owner_id),
        title=css.unescape(params.get("md_title") or options["mvData"]["title"]),
        thumb=params.get("jpg") or params.get("short_video_cover"),
        date=params["date"],
        formats=tuple(_extract_formats_legacy(params)),
        embed=extract_embed(),
    )


@aio.to_thread
def _parse_video(video: dict[str, Any]) -> Video:
    return deserialize(
        Video,
        video,
        thumb=thumbs[-1]["url"] if (thumbs := video.get("image")) else None,
        formats=tuple(_extract_formats(video)),
        embed=video.get("files", {}).get("external"),
    )


def _extract_formats(data: dict[str, Any]) -> Generator[Format]:
    for name, value in data.get("files", {}).items():
        if not value or type(value) is not str or not value.startswith(("//", "http")):
            continue

        url = VKCrawler.parse_url(value)

        match name.partition("_"):
            case ["mp4", _, res]:
                yield Format(name=name, url=url, height=int(res))
            case ["hls", *_]:
                yield Format(name=name, url=url, hls=True)
            case _:
                continue


def _extract_formats_legacy(data: dict[str, Any]) -> Generator[Format]:
    for name, value in data.items():
        if not value or type(value) is not str or not value.startswith(("//", "http")):
            continue

        url = VKCrawler.parse_url(value)

        if name.startswith("hls") and name != "hls_live_playback":
            yield Format(name=name, url=url, hls=True)

        elif name in {"extra_data", "live_mp4", "postlive_mp4"}:
            yield Format(name=name, url=url)

        elif m := re.search(r"^(?:url|cache)(\d+)", name):
            yield Format(name=name, url=url, height=int(m.group(1)))


def _parse_photo_legacy(photo: dict[str, Any]) -> Photo:
    origin = VKCrawler.parse_url(base) if (base := photo.get("base")) else None

    def sources() -> Iterable[PhotoSize]:
        for name, src in photo.items():
            if not name.endswith("_src"):
                continue

            try:
                _url, width, height = photo[name.removesuffix("src")]
            except ValueError:
                width = height = None

            url = VKCrawler.parse_url(src, origin)

            yield PhotoSize(type=name.removesuffix("_src"), width=width, height=height, url=_unblur(url))

    owner_id, _, photo_id = photo["id"].partition("_")
    return Photo(
        owner_id=int(owner_id),
        id=int(photo_id),
        date=int(css.select(css.soup(photo["date"]), "[data-date]", "data-date")),
        sources=tuple(sources()),
    )


def _unblur(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    return url.with_path(url.path.replace("/impf/", "/").replace("/impg/", "/"), keep_query=True, keep_fragment=True)


def _parse_photo(photo: dict[str, Any]) -> Photo:
    origin = VKCrawler.parse_url(base) if (base := photo.get("base")) else None

    def parse_src(size: dict[str, Any], name: str | None = None):
        url = VKCrawler.parse_url(size["url"], origin)
        return PhotoSize.parse(size, type=name or size["type"], url=_unblur(url))

    def sources() -> Iterable[PhotoSize]:
        if orig := photo.get("orig_photo"):
            yield parse_src(orig, "orig")

        yield from map(parse_src, photo["sizes"])

    return Photo.parse(photo, sources=tuple(sources()))
