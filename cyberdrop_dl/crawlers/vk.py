from __future__ import annotations

import base64
import contextlib
import dataclasses
import re
from typing import TYPE_CHECKING, Any, ClassVar, Unpack, override

from cyberdrop_dl import aio
from cyberdrop_dl.cache import disk_cached_method
from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedDomains, SupportedPaths, URLConfig
from cyberdrop_dl.exceptions import DDOSGuardError, ScrapeError
from cyberdrop_dl.mediaprops import Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import b64_pad, css
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator, Iterable

    from cyberdrop_dl.clients.request import RequestParams
    from cyberdrop_dl.clients.response import AbstractResponse
    from cyberdrop_dl.constants import HttpMethod
    from cyberdrop_dl.url_objects import ScrapeItem


@URLConfig(allow_empty_path=True)
class VKCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = "vkvideo.ru", "vkvideo.com", "vk.ru", "vk.com"
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/clip<owner_id>_<video_id>",
            "/video<owner_id>_<video_id>",
            "/video_ext.php?oid=<owner_id>&id=<video_id>",
        ),
        "User / Group photos": (
            "/id<owner_id>",
            "/public<owner_id>",
            "/albums<owner_id>",
            "/photos<owner_id>",
            "@<owner_screen_name>",
            "<owner_screen_name>",
        ),
        "Album": "/album<owner_id>_<album_id>",
        "Wall": "/wall<owner_id>_<wall_id>",
        "Tagged photos": "/tag<owner_id>",
    }
    DOMAIN: ClassVar[str] = "vk"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vk.com")
    FOLDER_DOMAIN: ClassVar[str] = "VK"

    @staticmethod
    @override
    def __db_path__(url: AbsoluteHttpURL, /) -> str:
        return url.with_query(sorted(url.query.items())).without_query_params("token").path_qs

    def __post_init__(self) -> None:
        self.update_cookies({"remixlang": 3})
        self.api: VKAPI = VKAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        query = scrape_item.url.query
        match scrape_item.url.parts[1:]:
            case ["video_ext.php"] if (oid := query.get("oid")) and (vid := query.get("id")):
                await self.video(scrape_item, oid, vid)

            case [] if redirect := query.get("to"):
                self.redirect(scrape_item, redirect)

            case [owner, "clips" | "all" | "donut" as kind]:
                kind = "videos" if kind == "all" else kind
                await self.owner_videos(scrape_item, owner.removeprefix("@"), kind)

            case [slug]:
                if video := _extract_id(slug, "clip", "video", composed=True):
                    owner_id, _, video_id = video.partition("_")
                    await self.video(scrape_item, owner_id, video_id)
                elif owner_id := _extract_id(slug, "albums", "photos", "id", "public", "@"):
                    await self.owner(scrape_item, owner_id)
                elif album := _extract_id(slug, "album", composed=True):
                    owner_id, _, album_id = album.partition("_")
                    await self.album(scrape_item, owner_id, album_id)
                elif wall := _extract_id(slug, "wall", composed=True):
                    owner_id, _, wall_id = wall.partition("_")
                    await self.wall(scrape_item, owner_id, wall_id)
                elif owner_id := _extract_id(slug, "tag"):
                    await self.tag(scrape_item, owner_id)
                else:
                    raise ValueError
            case _:
                raise ValueError

    @error_handling_wrapper
    def redirect(self, scrape_item: ScrapeItem, to: str) -> None:
        url = base64.urlsafe_b64decode(b64_pad(to)).decode("utf8")
        self.handle_external_links(scrape_item.create_child(self.parse_url(url)))

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, owner_id: str, video_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        video = await self.api.get_video(owner_id, video_id, list_id=scrape_item.url.query.get("list"))
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

    @error_handling_wrapper
    async def owner(self, scrape_item: ScrapeItem, owner_id: str) -> None:
        owner = await self.api.resolve_owner(owner_id)
        scrape_item.setup_as_profile(self.create_title(owner.full_name))
        scrape_item.append_folders("photos")
        await self._iter_photos(scrape_item, f"photos{owner.id}")

    @error_handling_wrapper
    async def owner_videos(self, scrape_item: ScrapeItem, owner_id: str, kind: str) -> None:
        owner = await self.api.resolve_owner(owner_id)
        scrape_item.setup_as_profile(self.create_title(owner.full_name))
        scrape_item.append_folders(kind)
        async with self.new_task_group() as tg:
            async for video in self.api.videos(scrape_item.url):
                prefix = "clip" if video.type == "short_video" else "video"
                url = self.PRIMARY_URL / f"{prefix}{video.owner_id}_{video.id}"
                tg.create_task(self.video_task(scrape_item.create_child(url), video))
                scrape_item.add_children()

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, owner_id: str, album_id: str) -> None:
        owner = await self.api.resolve_owner(owner_id)
        scrape_item.setup_as_profile(self.create_title(owner.full_name))
        scrape_item.append_folders(f"album_{album_id}")
        await self._iter_photos(scrape_item, f"album{owner_id}_{album_id}")

    @error_handling_wrapper
    async def wall(self, scrape_item: ScrapeItem, owner_id: str, wall_id: str) -> None:
        owner = await self.api.resolve_owner(owner_id)
        scrape_item.setup_as_profile(self.create_title(owner.full_name))
        scrape_item.append_folders(f"wall_{wall_id}")
        await self._iter_photos(scrape_item, f"wall{owner_id}_{wall_id}")

    @error_handling_wrapper
    async def tag(self, scrape_item: ScrapeItem, owner_id: str) -> None:
        owner = await self.api.resolve_owner(owner_id)
        scrape_item.setup_as_profile(self.create_title(owner.full_name))
        scrape_item.append_folders("tagged")
        await self._iter_photos(scrape_item, f"tag{owner_id}")

    async def _iter_photos(self, scrape_item: ScrapeItem, list_id: str) -> None:
        async with self.new_task_group() as tg:
            async for photo in self.api.photos(list_id):
                tg.create_task(self._photo(scrape_item.create_child(self.PRIMARY_URL / f"photo{photo.id}"), photo))
                scrape_item.add_children()

    @error_handling_wrapper
    async def _photo(self, scrape_item: ScrapeItem, photo: Photo) -> None:
        best = max(photo.sources, key=lambda s: s.score)
        filename, ext = self.get_filename_and_ext(best.url.name, assume_ext=".jpg")
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            best.url.name,
            ext,
            custom_filename=self.create_custom_filename(filename, ext, file_id=photo.id),
            metadata=photo,
            debrid_link=best.url,
        )


@dataclasses.dataclass(slots=True, frozen=True)
class Owner:
    id: int
    screen_name: str
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None

    @property
    def full_name(self) -> str:
        return " ".join(filter(None, (self.first_name, self.last_name))) or self.name or self.screen_name


@dataclasses.dataclass(slots=True, frozen=True)
class Format:
    name: str
    url: AbsoluteHttpURL
    height: int | None = None
    hls: bool = False

    @property
    def score(self) -> tuple[bool, int]:
        return (not self.hls, self.height or 0)


@dataclasses.dataclass(slots=True, frozen=True)
class Video:
    id: int
    owner_id: int
    title: str
    thumb: str | None
    date: int
    embed: str | None
    formats: tuple[Format, ...]
    type: str = "video"

    @property
    def slug(self) -> str:
        return f"{self.owner_id}_{self.id}"


@dataclasses.dataclass(slots=True, frozen=True)
class PhotoSrc:
    SIZES: ClassVar[tuple[str, ...]] = ("base", "s", "m", "x", "o", "p", "q", "r", "y", "z", "w")  # worst to best
    name: str
    res: Resolution
    url: AbsoluteHttpURL

    @property
    def score(self) -> int:
        try:
            return self.SIZES.index(self.name)
        except ValueError:
            raise ScrapeError(422, f"Unknown size for {self}") from None


@dataclasses.dataclass(slots=True, frozen=True)
class Photo:
    id: str
    uploaded: int
    sources: tuple[PhotoSrc, ...]
    desc: str | None = None


@dataclasses.dataclass(slots=True, frozen=True)
class OwnerSolution:
    id: int
    type: str


@dataclasses.dataclass(slots=True, frozen=True)
class CatalogSection:
    id: str
    next_from: str | None
    videos: list[dict[str, Any]]


@HTTPConfig(impersonate=True)
class VKAPI(API):
    # https://dev.vk.ru/en/reference
    APP_ID: ClassVar[str] = "6287487"
    VERSION: ClassVar[str] = "5.289"
    CLIENT_ID: ClassVar[str] = "52461373"
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.vkvideo.ru")

    @override
    @contextlib.asynccontextmanager
    async def request(
        self, url: AbsoluteHttpURL, /, method: HttpMethod = "GET", **kwargs: Unpack[RequestParams]
    ) -> AsyncGenerator[AbstractResponse[Any]]:
        async with super().request(url, method, **kwargs) as resp:
            if resp.url.name == "challenge.html":
                raise DDOSGuardError(f"JS challenge from VK: {resp.url}")

            yield resp

    @disk_cached_method(ttl=86400)
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

    async def get_user(self, screen_name_or_id: str | int) -> Owner:
        resp = await self.method("users.get", {"user_ids": str(screen_name_or_id)})
        if not resp:
            raise ScrapeError(404, f"User not found: {screen_name_or_id}")
        return deserialize(Owner, resp[0])

    async def get_group(self, screen_name_or_id: str | int) -> Owner:
        resp = await self.method("groups.getById", {"group_ids": str(screen_name_or_id)})
        groups = resp.get("groups")
        if not groups:
            raise ScrapeError(404, f"Group not found: {screen_name_or_id}")
        return deserialize(Owner, groups[0])

    async def method(self, method: str, data: dict[str, Any]) -> Any:
        data["access_token"] = await self.access_token()
        url = (self.ENTRYPOINT / "method" / method).with_query(v=self.VERSION, client_id=self.CLIENT_ID)
        resp = await self.request_json(url, "POST", data=data)
        if error := resp.get("error"):
            raise ScrapeError(401, error.get("error_msg"))
        return resp["response"]

    async def get_video(self, owner_id: str, video_id: str, *, list_id: str | None = None) -> Video:
        full_id = f"{owner_id}_{video_id}"
        data = {"videos": full_id}
        if list_id:
            data["album_id"] = list_id
        resp = await self.method("video.get", data)
        items = resp.get("items")
        if not items:
            raise ScrapeError(404)
        return _parse_video_api(items[0])

    async def get_video_legacy(self, owner_id: str, video_id: str, *, list_id: str | None = None) -> Video:
        # This may trigger a JS bot check
        data = {
            "act": "show",
            "video": f"{owner_id}-{video_id}",
            "al": 1,
        }
        if list_id:
            data["list"] = list_id

        payload = await self.request_payload("al_video.php", data)
        return await _parse_video(payload, owner_id, video_id)

    async def request_payload(self, path: str, data: dict[str, Any]) -> list[Any]:
        url = self.PRIMARY_URL / path
        resp = await self.request_json(
            url,
            data=data,
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

    async def resolve_owner(self, screen_name: str) -> Owner:
        owner = await self.method("utils.resolveScreenName", {"screen_name": screen_name})
        owner_id, owner_type = map(owner.get, ("object_id", "type"))
        match owner_type:
            case "group":
                resolve = self.get_group
            case "user":
                resolve = self.get_user
            case _:
                raise ScrapeError(422, f"Unsupported owner type: {owner}")

        return await resolve(owner_id)

    async def photos(self, list_id: str, *, offset: int = 0) -> AsyncGenerator[Photo]:
        data = {
            "act": "show",
            "al": "1",
            "direction": "1",
            "list": list_id,
            "offset": offset,
        }

        seen: set[str] = set()
        while True:
            payload = await self.request_payload("al_photos.php", data)
            total, photos = payload[1], payload[3]
            offset += len(photos)
            found_new_photos: bool = False
            for photo in map(_parse_photo, photos):
                if photo.id not in seen:
                    seen.add(photo.id)
                    found_new_photos = True
                    yield photo

            if not found_new_photos or offset >= total:
                break

            data["offset"] = offset

    async def catalog_get_video(self, url: AbsoluteHttpURL) -> CatalogSection:
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

    async def catalog_get_section(self, section_id: str, start_from: str) -> CatalogSection:
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

    async def videos(self, url: AbsoluteHttpURL, *, count: int = 20) -> AsyncGenerator[Video]:
        section = await self.catalog_get_video(url)
        seen: set[str] = set()
        while True:
            found_new_videos: bool = False
            for video in map(_parse_video_api, section.videos):
                if video.slug not in seen:
                    seen.add(video.slug)
                    found_new_videos = True
                    yield video

            if not found_new_videos or len(section.videos) < count or not section.next_from:
                break

            section = await self.catalog_get_section(section.id, section.next_from)


def _extract_formats(data: dict[str, Any]) -> Generator[Format]:
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


def _extract_id(slug: str, *prefixes: str, composed: bool = False) -> str | None:
    for prefix in prefixes:
        if slug.startswith(prefix):
            target = slug.removeprefix(prefix)
            if composed != ("_" in target):
                raise ValueError(target)
            return target


@aio.to_thread
def _parse_video(payload: list[Any], owner_id: str, video_id: str) -> Video:
    html, options = payload[1], payload[-1]
    params = options["player"]["params"][0]
    if params.get("live") == 2:
        raise ScrapeError(422, "Live streams are not supported")

    def extract_embed():
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
        formats=tuple(_extract_formats(params)),
        embed=extract_embed(),
    )


def _parse_video_api(video: dict[str, Any]) -> Video:
    return deserialize(
        Video,
        video,
        thumb=thumbs[-1]["url"] if (thumbs := video.get("image")) else None,
        formats=tuple(_extract_api_formats(video)),
        embed=video["files"].get("external"),
    )


def _extract_api_formats(data: dict[str, Any]) -> Generator[Format]:
    for name, value in data["files"].items():
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


def _parse_photo(photo: dict[str, Any]) -> Photo:
    def sources() -> Iterable[PhotoSrc]:
        origin = VKCrawler.parse_url(base) if (base := photo.get("base")) else None

        for name, src in photo.items():
            if not name.endswith("_src"):
                continue

            try:
                _url, width, height = photo[name.removesuffix("src")]
            except ValueError:
                res = Resolution.unknown()
            else:
                res = Resolution(width, height)

            url = VKCrawler.parse_url(src, origin)
            unblurred_url = url.with_path(
                url.path.replace("/impf/", "/").replace("/impg/", "/"), keep_query=True, keep_fragment=True
            )

            yield PhotoSrc(name=name.removesuffix("_src"), res=res, url=unblurred_url)

    return deserialize(
        Photo,
        photo,
        uploaded=int(css.select(css.soup(photo["date"]), "[data-date]", "data-date")),
        sources=tuple(sources()),
    )
