# https://dev.vk.ru/en/reference
from __future__ import annotations

import asyncio
import contextlib
import re
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, ClassVar, Final, Literal, Unpack, override

from typing_extensions import deprecated

from cyberdrop_dl.cache import async_lru_cache, disk_cached_method
from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import API
from cyberdrop_dl.crawlers.vk import full_res_img, try_parse_url
from cyberdrop_dl.crawlers.vk.types import (
    Audio,
    AudioPlaylist,
    CatalogSection,
    Format,
    Owner,
    Photo,
    PhotoSize,
    Post,
    Video,
)
from cyberdrop_dl.exceptions import DDOSGuardError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, parse_url

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator, Iterable

    from cyberdrop_dl.clients.request import RequestParams
    from cyberdrop_dl.clients.response import AbstractResponse
    from cyberdrop_dl.constants import HttpMethod


def _entity_id(owner_id: str | int, item_id: str | int, access_key: str | int | None = None) -> str:
    # Access key is for private videos
    entity = f"{owner_id}_{item_id}"
    if access_key is not None:
        entity += f"_{access_key}"

    return entity


ERROR_CODES: Final = (
    dict.fromkeys((30, 200, 201, 202, 203), HTTPStatus.FORBIDDEN)
    | dict.fromkeys((6, 9, 17, 18, 29), HTTPStatus.TOO_MANY_REQUESTS)
    | dict.fromkeys((1, 10), HTTPStatus.INTERNAL_SERVER_ERROR)
    | dict.fromkeys((5, 7), HTTPStatus.UNAUTHORIZED)
)


@HTTPConfig(rate_limit=(2, 1))
class VKAPI(API):
    APP_ID: ClassVar[str] = "6287487"
    VERSION: ClassVar[str] = "5.289"
    CLIENT_ID: ClassVar[str] = "6287487"
    VIDEO_ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.vkvideo.ru")
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://web.api.vk.ru")
    VK: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vk.com")

    def __post_init__(self) -> None:
        self.owner_by_id = async_lru_cache(self._owner_by_id)
        self.legacy: VKLegacy = VKLegacy(self)
        self.catalog: VKCatalog = VKCatalog(self)
        self.audio: VKAudio = VKAudio(self)

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

    async def resolve_owner(self, screen_name: str) -> Owner:
        try:
            owner_id = int(screen_name)
        except ValueError:
            return await self.owner_by_screen_name(screen_name)
        else:
            return await self.owner_by_id(owner_id)

    async def _owner_by_id(self, owner_id: int) -> Owner:
        errors: list[Exception] = []
        for method in (self.get_user, self.get_group):
            try:
                return await method(owner_id)
            except ScrapeError as e:
                errors.append(e)

        raise BaseExceptionGroup("", tuple(errors))

    async def owner_by_screen_name(self, screen_name: str) -> Owner:
        screen_name = screen_name.removeprefix("@")
        assert screen_name
        for found in self.owner_by_id.cache.values():
            if found.screen_name == screen_name:
                return found

        if not (owner := await self.method("utils.resolveScreenName", {"screen_name": screen_name})):
            raise ScrapeError(404, f"No user found with {screen_name = }")

        owner_id, owner_type = owner["object_id"], owner["type"]
        match owner_type:
            case "group":
                resolve = self.get_group
            case "user":
                resolve = self.get_user
            case _:
                raise ScrapeError(422, f"Unsupported owner type: {owner}")

        return await resolve(owner_id)

    async def get_user(self, screen_name_or_id: str | int) -> Owner:
        resp = await self.method("users.get", {"user_ids": str(screen_name_or_id)})
        if not resp:
            raise ScrapeError(404, f"User not found: {screen_name_or_id}")
        return Owner.parse(resp[0], type="user")

    async def get_group(self, group_id: str | int) -> Owner:
        resp = await self.method("groups.getById", {"group_ids": str(group_id).lstrip("-")})
        groups = resp.get("groups")
        if not groups:
            raise ScrapeError(404, f"Group not found: {group_id}")
        return Owner.parse(groups[0])

    async def get_post(self, owner_id: str, post_id: str) -> Post:
        resp = await self.method("wall.getById", {"posts": f"{owner_id}_{post_id}"})
        items = resp.get("items")
        if not items:
            raise ScrapeError(404)
        return Post.parse(items[0])

    async def get_wall(
        self, domain: str, *, offset: int = 0, filter_: Literal["all", "others", "owner"] = "all"
    ) -> AsyncGenerator[Post]:
        data = {"domain": domain, "filter": filter_, "offset": offset}
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

    async def get_video(self, owner_id: str, video_id: str, *, access_key: str | None = None) -> Video:
        resp = await self.method("video.get", {"videos": _entity_id(owner_id, video_id, access_key)})
        items = resp.get("items")
        if not items:
            raise ScrapeError(404)
        return Video.parse(items[0])

    async def get_videos(self, url: AbsoluteHttpURL) -> AsyncGenerator[Video]:
        section = await self.catalog.get_video(url)
        seen: set[str] = set()
        while True:
            found_new_videos: bool = False
            for video in map(Video.parse, section.videos):
                if video.slug not in seen:
                    seen.add(video.slug)
                    found_new_videos = True
                    yield video

            if not found_new_videos or not section.next_from:
                break

            section = await self.catalog.get_section(section.id, section.next_from)

    @deprecated("DO NOT USE. This endpoint works but all image src files are 404")
    async def get_photo(self, owner_id: str, photo_id: str, album_id: str | None = None) -> Photo:
        album_options = (album_id,) if album_id else ("profile", "wall")
        for aid in album_options:
            resp = await self.method(
                "photos.get",
                {
                    "owner_id": owner_id,
                    "album_id": aid,
                    "photo_ids": photo_id,
                    "photo_sizes": 1,
                },
            )
            if items := resp.get("items"):
                return Photo.parse(items[0])

        raise ScrapeError(404)

    async def get_photo_auth(self, owner_id: str, photo_id: str) -> Photo:
        # NOT supported with anonymous token
        data = {
            "photos": f"{owner_id}_{photo_id}",
            "photo_sizes": 1,
        }
        resp = await self.method("photos.getById", data)
        items = resp.get("items")
        if not items:
            raise ScrapeError(404)
        return Photo.parse(items[0])


class VKAudio(API.Endpoint[VKAPI]):
    async def get(self, owner_id: str, audio_id: str, *, access_key: str | None = None) -> Audio:
        audios = await self.get_by_entity(_entity_id(owner_id, audio_id, access_key))
        if not audios:
            raise ScrapeError(404)
        return audios[0]

    async def get_by_entity(self, *entity_ids: str) -> list[Audio]:
        assert entity_ids
        resp = await self.api.method(
            "audio.getById",
            {
                "audios": ",".join(entity_ids),
                "photo_sizes": 1,
            },
        )
        return list(map(Audio.parse, resp))

    async def get_playlist(self, owner_id: str, playlist_id: str, *, access_key: str | None = None) -> AudioPlaylist:
        data = {"playlist_id": playlist_id, "owner_id": owner_id}
        if access_key:
            data["access_key"] = access_key
        resp = await self.api.method("audio.getPlaylistById", data)
        if not resp:
            raise ScrapeError(404)
        return AudioPlaylist.parse(resp)

    async def get_ids(self, owner_id: str | int, playlist_id: str | int, access_key: str | None = None) -> list[str]:
        resp = await self.api.method(
            "audio.getIdsBySource",
            {
                "source": "playlist",
                "entity_id": _entity_id(owner_id, playlist_id, access_key),
            },
        )
        return [a["audio_id"] for a in resp["audios"]]


class VKCatalog(API.Endpoint[VKAPI]):
    async def get_video(self, url: AbsoluteHttpURL) -> CatalogSection:
        resp = await self.api.method(
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

    async def get_section(self, section_id: str, start_from: str) -> CatalogSection:
        resp = await self.api.method(
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


class VKLegacy(API.Endpoint[VKAPI]):
    # These methods may trigger a JS bot check
    async def request_payload(self, path: str, data: dict[str, Any]) -> list[Any]:
        resp = await self.api.request_json(
            url := self.api.VK / path,
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
        data = {
            "act": "show",
            "video": f"{owner_id}_{video_id}",
            "al": 1,
        }
        if access_key:
            data["list"] = access_key

        payload = await self.request_payload("al_video.php", data)
        return await asyncio.to_thread(_parse_video_legacy, payload, owner_id, video_id)

    async def get_photo(self, owner_id: str, photo_id: str) -> Photo:
        data = {
            "act": "show",
            "photo": f"{owner_id}_{photo_id}",
            "list": owner_id,
            "al": 1,
        }

        payload = await self.request_payload("al_photos.php", data)
        photos = payload[3]
        if not photos:
            raise ScrapeError(404)
        return await asyncio.to_thread(_parse_photo_legacy, photos[0])

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
            payload = await self.request_payload("al_photos.php", data)
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


def _extract_formats_legacy(data: dict[str, Any]) -> Generator[Format]:
    for name, value in data.items():
        if url := try_parse_url(value):
            if name.startswith("hls") and name != "hls_live_playback":
                yield Format(name, url, hls=True)

            elif name in {"extra_data", "live_mp4", "postlive_mp4"}:
                yield Format(name, url)

            elif m := re.search(r"^(?:url|cache)(\d+)", name):
                yield Format(name, url, height=int(m.group(1)))


def _parse_photo_legacy(photo: dict[str, Any]) -> Photo:
    origin = parse_url(base) if (base := photo.get("base")) else None
    owner_id, _, photo_id = photo["id"].partition("_")

    def sources() -> Iterable[PhotoSize]:
        for name, src in photo.items():
            if not name.endswith("_src"):
                continue

            try:
                _url, width, height = photo[name.removesuffix("src")]
            except ValueError:
                width = height = None

            url = parse_url(src, origin)

            yield PhotoSize(type=name.removesuffix("_src"), width=width, height=height, url=full_res_img(url))

    return Photo(
        owner_id=int(owner_id),
        id=int(photo_id),
        date=int(css.select(css.soup(photo["date"]), "[data-date]", "data-date")),
        sources=tuple(sources()),
    )
