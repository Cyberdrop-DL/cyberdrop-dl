from __future__ import annotations

import base64
import contextlib
import dataclasses
import json
import re
from typing import TYPE_CHECKING, Any, ClassVar, Self, Unpack, override

from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedDomains, SupportedPaths, URLConfig
from cyberdrop_dl.exceptions import DDOSGuardError, ScrapeError
from cyberdrop_dl.mediaprops import Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import b64_pad, css, extr_text, traversal
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
        "User photos": (
            "/id<owner_id>",
            "/public<owner_id>",
            "/albums<owner_id>",
            "/photos<owner_id>",
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
        self.api: VKAPI = VKAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        query = scrape_item.url.query
        match scrape_item.url.parts[1:]:
            case ["video_ext.php"] if (oid := query.get("oid")) and (vid := query.get("id")):
                video_id = f"{oid}_{vid}"
                await self.video(scrape_item, video_id)
            case [] if redirect := query.get("to"):
                self.redirect(scrape_item, redirect)
            case [slug] if not slug.startswith("@"):
                if video_id := _extract_id(slug, "clip", "video", composed=True):
                    await self.video(scrape_item, video_id)
                elif owner_id := _extract_id(slug, "albums", "photos", "id", "public"):
                    await self.user(scrape_item, owner_id)
                elif album := _extract_id(slug, "album", composed=True):
                    owner_id, _, album_id = album.partition("_")
                    await self.album(scrape_item, owner_id, album_id)
                elif wall := _extract_id(slug, "wall", composed=True):
                    owner_id, _, wall_id = wall.partition("_")
                    await self.wall(scrape_item, owner_id, wall_id)
                elif owner_id := _extract_id(slug, "tag"):
                    await self.tag(scrape_item, owner_id)
                else:
                    await self.page(scrape_item, slug)
            case _:
                raise ValueError

    @error_handling_wrapper
    def redirect(self, scrape_item: ScrapeItem, to: str) -> None:
        url = base64.urlsafe_b64decode(b64_pad(to)).decode("utf8")
        self.handle_external_links(scrape_item.create_child(self.parse_url(url)))

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        video = await self.api.video(video_id, list_id=scrape_item.url.query.get("list"))
        best_fmt = max(video.formats, key=lambda f: f.score)
        scrape_item.uploaded_at = video.uploaded_at
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
                file_id=video_id,
                resolution=info.resolution if info else best_fmt.height,
            ),
            thumbnail=video.thumb,
            debrid_link=debrid_url,
            metadata=video,
        )

    @error_handling_wrapper
    async def user(self, scrape_item: ScrapeItem, user_id: str) -> None:
        user = await self.api.owner(user_id)
        scrape_item.setup_as_profile(self.create_title(user.full_name))
        scrape_item.append_folders("photos")
        await self._iter_photos(scrape_item, f"photos{user.id}")

    @error_handling_wrapper
    async def page(self, scrape_item: ScrapeItem, screen_name: str) -> None:
        owner = await self.api.resolve_owner(screen_name)
        scrape_item.setup_as_profile(self.create_title(owner.full_name))
        scrape_item.append_folders("photos")
        await self._iter_photos(scrape_item, f"photos{owner.id}")

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, user_id: str, album_id: str) -> None:
        user = await self.api.owner(user_id)
        scrape_item.setup_as_profile(self.create_title(user.full_name))
        scrape_item.append_folders(f"album_{album_id}")
        await self._iter_photos(scrape_item, f"album{user_id}_{album_id}")

    @error_handling_wrapper
    async def wall(self, scrape_item: ScrapeItem, user_id: str, wall_id: str) -> None:
        user = await self.api.owner(user_id)
        scrape_item.setup_as_profile(self.create_title(user.full_name))
        scrape_item.append_folders(f"wall_{wall_id}")
        await self._iter_photos(scrape_item, f"wall{user_id}_{wall_id}")

    @error_handling_wrapper
    async def tag(self, scrape_item: ScrapeItem, user_id: str) -> None:
        user = await self.api.owner(user_id)
        scrape_item.setup_as_profile(self.create_title(user.full_name))
        scrape_item.append_folders("tagged")
        await self._iter_photos(scrape_item, f"tag{user_id}")

    async def _iter_photos(self, scrape_item: ScrapeItem, list_id: str) -> None:
        async with self.new_task_group() as tg:
            async for photo in self.api.photos(list_id):
                tg.create_task(self._photo(scrape_item, photo))
                scrape_item.add_children()

    async def _photo(self, scrape_item: ScrapeItem, photo: Photo) -> None:
        best = max(photo.sources, key=lambda s: s.score)
        with self.catch_errors(best.url):
            filename, ext = self.get_filename_and_ext(best.url.name)
            await self.handle_file(best.url, scrape_item, best.url.name, ext, custom_filename=filename, metadata=photo)


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
    title: str
    thumb: str | None
    embed_html: str
    uploaded_at: int
    formats: tuple[Format, ...]


@dataclasses.dataclass(slots=True, frozen=True)
class PhotoSrc:
    SIZES: ClassVar[tuple[str, ...]] = ("s", "m", "x", "o", "p", "q", "r", "y", "z", "w")  # worst to best
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

    @classmethod
    def _parse_sources(cls, photo: dict[str, Any]) -> Iterable[PhotoSrc]:
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

    @classmethod
    def parse(cls, photo: dict[str, Any]) -> Self:
        return deserialize(
            cls,
            photo,
            uploaded=int(css.select(css.soup(photo["date"]), "[data-date]", "data-date")),
            sources=tuple(cls._parse_sources(photo)),
        )


@HTTPConfig(impersonate=True)
class VKAPI(API):
    @override
    @contextlib.asynccontextmanager
    async def request(
        self, url: AbsoluteHttpURL, /, method: HttpMethod = "GET", **kwargs: Unpack[RequestParams]
    ) -> AsyncGenerator[AbstractResponse[Any]]:
        async with super().request(url, method, **kwargs) as resp:
            if resp.url.name == "challenge.html":
                raise DDOSGuardError(f"JS challenge from VK: {resp.url}")

            yield resp

    async def video(self, video_id: str, *, list_id: str | None = None) -> Video:
        url = self.PRIMARY_URL / "al_video.php"
        data = {
            "act": "show",
            "video": video_id,
            "al": 1,
        }
        if list_id:
            data["list"] = list_id

        resp = await self.request_json(
            url,
            data=data,
            impersonate=True,
            headers={
                "Referer": str(url),
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        payload = _payload(resp)
        html, options = payload[1], payload[-1]
        params = options["player"]["params"][0]
        if params.get("live") == 2:
            raise ScrapeError(422, "Live streams are not supported")

        return Video(
            title=css.unescape(params.get("md_title") or options["mvData"]["title"]),
            thumb=params.get("jpg") or params.get("short_video_cover"),
            uploaded_at=params["date"],
            formats=tuple(_extract_formats(params)),
            embed_html=html,
        )

    async def _prefetch(self, url: AbsoluteHttpURL) -> Any:
        html = await self.request_text(url)
        content = extr_text(html, '"apiPrefetchCache":', "});")
        return json.loads(content)

    async def owner(self, owner_id: str) -> Owner:
        domain = owner_id

        if not domain.startswith(("id", "public")):
            domain = f"public{owner_id.lstrip('-')}" if owner_id.startswith("-") else f"id{owner_id}"

        pf_data = await self._prefetch(self.PRIMARY_URL / domain)
        _, owner = traversal.find_obj(pf_data, validate={"id": int(owner_id.lstrip("-"))})
        return deserialize(Owner, owner)

    async def resolve_owner(self, screen_name: str) -> Owner:
        pf_data = await self._prefetch(self.PRIMARY_URL / screen_name)
        _, owner = traversal.find_obj(pf_data, "id", validate={"screen_name": screen_name})
        return deserialize(Owner, owner)

    async def photos(self, list_id: str, *, offset: int = 0) -> AsyncGenerator[Photo]:
        url = self.PRIMARY_URL / "al_photos.php"
        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": str(self.PRIMARY_URL / list_id),
        }

        data = {
            "act": "show",
            "al": "1",
            "direction": "1",
            "list": list_id,
            "offset": offset,
        }

        seen: set[str] = set()
        while True:
            resp = await self.request_json(url, "POST", headers=headers, data=data)
            payload = _payload(resp)
            total, photos = payload[1], payload[3]
            offset += len(photos)
            found_new_photos: bool = False
            for photo in map(Photo.parse, photos):
                if photo.id not in seen:
                    seen.add(photo.id)
                    found_new_photos = True
                    yield photo

            if not found_new_photos or offset >= total:
                break

            data["offset"] = offset


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


def _payload(resp: dict[str, Any]) -> list[Any]:
    code, payload = resp["payload"]
    match code:
        case "8":
            raise ScrapeError(403, payload[0].strip('"'))
        case "3":
            raise ScrapeError(401)
        case _:
            return payload
