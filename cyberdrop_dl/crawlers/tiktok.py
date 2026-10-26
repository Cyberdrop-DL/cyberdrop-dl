from __future__ import annotations

import asyncio
import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

from cyberdrop_dl import aio
from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths, auto_task_id
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem
from cyberdrop_dl.utils.dataclass import deserialize
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from cyberdrop_dl.url_objects import ScrapeItem


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Author:
    id: str
    unique_id: str
    nickname: str

    def __str__(self) -> str:
        return f"@{self.unique_id}"


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class Post:
    id: str
    title: str
    create_time: int
    size: int
    author: Author
    music_info: MusicInfo
    play: str | None = None
    is_src_quality: bool = False
    cover: str | None = None
    images: list[str] = dataclasses.field(default_factory=list)

    @property
    def type(self) -> str:
        return "photo" if self.images else "video"

    @property
    def web_path(self) -> str:
        return f"{self.author}/{self.type}/{self.id}"

    @classmethod
    def from_dict(cls, video: Mapping[str, Any], *, is_src_quality: bool = False) -> Self:
        return deserialize(
            cls,
            video,
            images=video.get("images") or [],
            author=deserialize(Author, (video["author"])),
            music_info=deserialize(MusicInfo, (video["music_info"])),
            id=video.get("id") or video["video_id"],
            play=video.get("play") or video["play_url"],
            is_src_quality=is_src_quality,
        )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class MusicInfo:
    title: str
    id: str
    original: bool
    play: str | None = None

    @property
    def web_path(self) -> str:
        safe_title = self.title.replace(" ", "-").lower()
        if "original-sound" in safe_title or "original-audio" in safe_title:
            safe_title = "original-audio"
        return f"music/{safe_title}-{self.id}"


@HTTPConfig(rate_limit=(1, 2))
class TikTokCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "User": "/@<user>",
        "Video": (
            "/@<user>/video/<video_id>",
            "/@/video/<video_id>",
            "/share/video/<video_id>",
        ),
        "Photo": (
            "/@<user>/photo/<photo_id>",
            "/@/photo/<photo_id>",
            "/share/photo/<photo_id>",
        ),
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.tiktok.com")
    DOMAIN: ClassVar[str] = "tiktok"
    FOLDER_DOMAIN: ClassVar[str] = "TikTok"
    DEFAULT_POST_TITLE_FORMAT: ClassVar[str] = "{date:%Y-%m-%d} - {id}"

    @property
    def original(self) -> bool:
        return self.config.crawlers.tiktok.original

    def __post_init__(self) -> None:
        self.api: TikWMAPI = TikWMAPI.from_crawler(self)
        cookie_name = "sessionid"
        if value := self.cookies.get(cookie_name):
            self.log.info(f"Found {cookie_name} cookies")
            self.api.__http_ctx__.headers["x-proxy-cookie"] = f"{cookie_name}={value}"

        self.client.cookies.clear_domain(self.PRIMARY_URL.host)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_, "video" | "photo" | "v" as kind, media_id]:
                media_id = media_id.removesuffix(".html")
                await self.post(scrape_item, kind, media_id)
            case [profile] if profile.startswith("@"):
                await self.profile(scrape_item, profile.removeprefix("@"))
            case _:
                raise ValueError

    @error_handling_wrapper
    async def profile(self, scrape_item: ScrapeItem, profile_id: str) -> None:
        scrape_item.setup_as_profile("")
        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            async for post in self.api.profile_posts(profile_id):
                url = self.PRIMARY_URL / post.web_path
                new_item = scrape_item.create_child(url)
                tg.create_task(self._post_task(new_item, post))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def post(self, scrape_item: ScrapeItem, kind: str, media_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        if kind != "photo" and self.original:
            post = await self.api.post_src_quality(media_id)
        else:
            post = await self.api.post(media_id)

        await self._post(scrape_item, post)

    async def _post(self, scrape_item: ScrapeItem, post: Post) -> None:
        scrape_item.url = self.PRIMARY_URL / post.web_path
        scrape_item.append_folders(self.create_title(post.author.unique_id, post.id))
        post_title = self.create_separate_post_title(post.title, post.id, post.create_time)
        scrape_item.setup_as_album(post_title, album_id=post.id)
        scrape_item.uploaded_at = post.create_time
        await aio.gather(
            self._handle_images(scrape_item, post),
            self._handle_audio(scrape_item, post),
            self._handle_video(scrape_item, post),
            fail_fast=False,
        )

    @auto_task_id
    @error_handling_wrapper
    async def _post_task(self, scrape_item: ScrapeItem, post: Post) -> None:
        if await self.check_complete(scrape_item.url):
            return

        if not post.images and self.original and not post.is_src_quality:
            post = await self.api.post_src_quality(post.id)

        await self._post(scrape_item, post)

    async def _handle_images(self, scrape_item: ScrapeItem, post: Post) -> None:
        async with aio.non_cancelling_taskgroup() as tg:
            for index, url in enumerate(post.images):
                link = self.parse_url(url, trim=False)
                img_url = self.PRIMARY_URL / post.web_path / str(index)
                filename = self.create_custom_filename(f"{post.id}_img{str(index).zfill(3)}", link.suffix)
                tg.create_task(
                    self.handle_file(
                        img_url,
                        scrape_item,
                        filename,
                        link.suffix,
                        debrid_link=link,
                    )
                )

    async def _handle_audio(self, scrape_item: ScrapeItem, post: Post) -> None:
        audio = post.music_info
        if not audio.play:
            return

        audio_url = self.parse_url(audio.play, trim=False)
        filename = self.create_custom_filename(audio.title, ext := ".mp3", file_id=audio.id)
        await self.handle_file(
            self.PRIMARY_URL / audio.web_path,
            scrape_item,
            audio.title + ext,
            ext,
            debrid_link=audio_url,
            custom_filename=filename,
        )

    async def _handle_video(self, scrape_item: ScrapeItem, post: Post) -> None:
        if not (post.size and post.play):
            return

        video_url = self.parse_url(post.play, trim=False)
        name = f"{post.id}{'_original'}" if post.is_src_quality else post.id
        filename, ext = self.get_filename_and_ext(f"{name}.mp4")
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            name + ext,
            ext,
            debrid_link=video_url,
            custom_filename=filename,
            thumbnail=post.cover,
        )

    @override
    def _prepare_media_item(self, media_item: MediaItem) -> None:
        if media_item.ext == ".mp3":
            media_item.download_folder /= "Audios"


def _check_json_resp(resp: dict[str, Any], _: Any) -> None:
    code = resp.get("code")
    if code != 0:
        msg = resp.get("msg", "")
        if "Url parsing is failed" in msg:
            raise ScrapeError(410)
        raise ScrapeError(422, message=f"{code = }, {msg}")


@HTTPConfig(headers={"X-Requested-With": "XMLHttpRequest"}, json_check=_check_json_resp)
class TikWMAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.tikwm.com/api")

    async def submit_task(self, media_id: str) -> str:
        submit_url = (self.ENTRYPOINT / "video/task/submit").with_query(url=media_id)
        resp = await self.request_json(submit_url)
        return resp["data"]["task_id"]

    async def post(self, media_id: str) -> Post:
        api_url = self.ENTRYPOINT.with_query(url=media_id)
        resp = await self.request_json(api_url)
        return Post.from_dict(resp["data"])

    async def post_src_quality(self, media_id: str) -> Post:
        task_id: str = await self.submit_task(media_id)
        self.log.info(f"trying to download {media_id = } with {task_id = }")
        return await self.wait_for_task(task_id)

    async def wait_for_task(self, task_id: str) -> Post:
        api_url = (self.ENTRYPOINT / "video/task/result").with_query(task_id=task_id)
        delays = (0.5, 1.5, 4)
        for delay in delays:
            try:
                await asyncio.sleep(delay)
                resp = await self.request_json(api_url)
            except ScrapeError:
                pass
            else:
                return Post.from_dict(resp["data"]["detail"], is_src_quality=True)

        msg = (
            f"[tiktok] Download {task_id = } was not ready after {len(delays)} attempts. Total wait time: {sum(delays)}"
        )
        raise ScrapeError(503, msg)

    async def profile_posts(self, profile_id: str, cursor: int = 0) -> AsyncGenerator[Post]:
        api_url = (self.ENTRYPOINT / "user/posts").with_query(unique_id=profile_id, count=50)
        while True:
            resp = await self.request_json(api_url.update_query(cursor=cursor), impersonate=True)
            data: dict[str, Any] = resp["data"]
            for post in data["videos"]:
                yield Post.from_dict(post)

            if not data["hasMore"]:
                break

            cursor = data["cursor"]
