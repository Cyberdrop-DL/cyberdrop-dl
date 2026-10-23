from __future__ import annotations

import base64
import re
from typing import TYPE_CHECKING, ClassVar, override

from cyberdrop_dl.crawlers.crawler import Crawler, SupportedDomains, SupportedPaths, URLConfig, auto_task_id
from cyberdrop_dl.crawlers.vk import full_res_img
from cyberdrop_dl.crawlers.vk.api import VKAPI
from cyberdrop_dl.crawlers.vk.types import Album, Audio, File, Graffiti, Link, Photo, PhotoSize, Post, Video
from cyberdrop_dl.exceptions import DownloadError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import b64_pad
from cyberdrop_dl.utils._url import remove_query_params
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


_PAGES_TYPES = (
    "album",
    "albums",
    "audio",
    "audios",
    "clip",
    "club",
    "doc",
    "event",
    "id",
    "market",
    "page",
    "photo",
    "post",
    "product",
    "public",
    "topic",
    "uslugi",
    "video",
    "videos",
    "wall",
    "wpt",
)

INNER_PAGES = {
    "about",
    "audio",
    "away.php",
    "blog",
    "clips",
    "games",
    "groups",
    "feed",
    "jobs",
    "join",
    "legal",
    "login",
    "mobile",
    "products",
    "technology",
    "services",
    "terms",
    "video",
}

_PAGE_REGEX = rf"^(?P<type>{'|'.join(_PAGES_TYPES)})(?P<owner_id>-?\d+)(?:_(?P<item_id>\d+))?"


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
        self.api: VKAPI = VKAPI.from_crawler(self)

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = full_res_img(
            super().transform_url(url).without_query_params("pl", "fromTrackCode")
        )  # TODO: support playlists

        match url.parts[1:]:
            case ["video_ext.php"] if (owner_id := url.query.get("oid")) and (vid := url.query.get("id")):
                url = VKVideoCrawler.PRIMARY_URL / f"video{owner_id}_{vid}"
            case [slug]:
                if slug.startswith("@") and "vkvideo" in url.host:
                    url = url / "all"
                if slug.startswith(("video", "clip")):
                    url = url.with_host(VKVideoCrawler.PRIMARY_URL.host)

            case ["clips", username]:
                url = VKVideoCrawler.PRIMARY_URL / f"@{username}" / "clips"
            case ["video", username] if username.startswith("@"):
                url = VKVideoCrawler.PRIMARY_URL / username / "all"
            case _:
                pass

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
            case [slug] if m := re.match(_PAGE_REGEX, slug):
                match m.groups():
                    case ["clip" | "video", str(owner_id), str(video_id)]:
                        await self.video(scrape_item, owner_id, video_id)
                    case _:
                        raise ValueError
            case _:
                raise ValueError

    @error_handling_wrapper
    async def owner_videos(self, scrape_item: ScrapeItem, owner_id: str, kind: str) -> None:
        owner = await self.api.resolve_owner(owner_id)
        scrape_item.setup_as_profile(self.create_title(owner.full_name))
        scrape_item.append_folders(kind)
        async with self.new_task_group() as tg:
            async for video in self.api.get_videos(scrape_item.url):
                url = self.PRIMARY_URL / video.web_path
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
        title = video.title or video.description or video.prefix
        if video.embed:
            new_item = scrape_item.create_child(self.parse_url(video.embed))
            new_item.setup_as_album(self.create_title(title, video.slug, force_album_id=True))
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
            title,
            ext := ".mp4",
            m3u8=m3u8,
            custom_filename=self.create_custom_filename(
                title,
                ext,
                file_id=video.slug,
                resolution=info.resolution if info else best_fmt.height,
            ),
            thumbnail=video.thumb,
            debrid_link=debrid_url,
            metadata=video,
        )


@URLConfig(allow_empty_path=True)
class VKCrawler(VKBaseCrawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = (
        "vk.ru",
        "vk.com",
        "vkontakte.ru",
        ".userapi.com",
        "vk.me",
        "mvk.com",
    )
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
            "/videos<owner_id>",
            "/videos/@username",
            "/clips/username",
        ),
        "Album": "/album<owner_id>_<album_id>",
        "Post": "/wall<owner_id>_<wall_id>",
        "Photo": "/photo<owner_id>_<photo_id>",
        "Redirect": (
            "/?to=<base64_url>",
            "/away.php?to=<url>",
        ),
        "Direct images": ".userapi.com/...",
    }

    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://vk.com")
    OLD_DOMAINS: ClassVar[tuple[str, ...]] = ("vk.cc",)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        url = scrape_item.url
        if "vkvideo" in url.host:
            self.handle_external_links(scrape_item)

        elif url.host.endswith(".userapi.com"):
            await self.direct_file(scrape_item)

        else:
            match url.parts[1:]:
                case [] | ["away.php"] if to := url.query.get("to"):
                    self.redirect(scrape_item, to)
                case [slug] if slug not in INNER_PAGES:
                    if m := re.match(_PAGE_REGEX, slug):
                        await self._match_page(scrape_item, m.groups())
                    else:
                        await self.wall(scrape_item, slug)
                case _:
                    raise ValueError

    async def _match_page(self, scrape_item: ScrapeItem, page: tuple[str | None, ...]) -> None:
        match page:
            case ["albums" | "photos", str(owner_id), None]:
                await self.photos(scrape_item, owner_id)
            case ["wall", str(owner_id), str(post_id)]:
                await self.post(scrape_item, owner_id, post_id)
            case ["photo", str(owner_id), str(photo_id)]:
                await self.photo(scrape_item, owner_id, photo_id)
            case ["id" | "public", str(owner_id), None]:
                await self.wall(scrape_item, owner_id)
            case ["videos", str(owner_id), None]:  # redirects to https://vkvideo.ru/@<username>
                await self.follow_redirect(scrape_item)
            case ["album", str(owner_id), str(album_id)]:
                if album_id == "00":
                    await self.wall(scrape_item, owner_id)
                else:
                    await self.album(scrape_item, owner_id, album_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    def redirect(self, scrape_item: ScrapeItem, to: str) -> None:
        url = to if to.startswith("http") else base64.urlsafe_b64decode(b64_pad(to)).decode("utf8")
        self.handle_external_links(scrape_item.create_child(self.parse_url(url)))

    @error_handling_wrapper
    async def photos(self, scrape_item: ScrapeItem, owner_id: str) -> None:
        raise NotImplementedError

    @error_handling_wrapper
    async def photo(self, scrape_item: ScrapeItem, owner_id: str, photo_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        owner = await self.api.resolve_owner(owner_id)
        scrape_item.setup_as_profile(self.create_title(owner.full_name))
        photo = await self.api.legacy.get_photo(owner_id, photo_id)
        await self._photo(scrape_item, photo)

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
                        photo = Photo.parse(attach["photo"])
                        url = self.PRIMARY_URL / photo.web_path
                        tg.create_task(self._photo(scrape_item.create_child(url), photo))

                    case "video":
                        vid = Video.parse(attach["video"])
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

    async def _select_best_src(self, photo: Photo) -> PhotoSize:
        for option in sorted(photo.sources, key=PhotoSize.score, reverse=True)[:3]:
            try:
                async with self.request(option.url, "HEAD") as _:
                    ...
            except DownloadError as e:
                if e.status != 404:
                    raise
                self.log.warning("Unable to get image [type %s] for photo %s, skipping...", option.type, photo.slug)
            else:
                return option

        raise ScrapeError(404, "None of the image sources are available")

    @error_handling_wrapper
    async def _photo(self, scrape_item: ScrapeItem, photo: Photo) -> None:
        best = await self._select_best_src(photo)
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
