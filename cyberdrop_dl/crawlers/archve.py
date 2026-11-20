from __future__ import annotations

import asyncio
import base64
import dataclasses
import hashlib
import time
from typing import ClassVar, override

from cyberdrop_dl import aio
from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths, auto_task_id
from cyberdrop_dl.exceptions import NoExtensionError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import b64_pad, css, extr_text
from cyberdrop_dl.utils.crypto import aes_cbc_decrypt, aes_unpad
from cyberdrop_dl.utils.errors import error_handling_wrapper


@HTTPConfig(probe_method="GET")
class ArchveCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/watch/<video_uuid>",
            "/e/<video_uuid>",
            "/d/<video_uuid>",
        ),
        "Album": "/albums/<album_id>",
        "User videos": "/u/<user_id>",
        "User albums": "/u/<user_id>/albums",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://archve.xyz")
    DOMAIN: ClassVar[str] = "archve"
    NEXT_PAGE_SELECTOR: ClassVar[str] = ".profile-pager a.btn:-soup-contains-own(Next)"

    def __post_init__(self) -> None:
        self.api: ArchveAPI = ArchveAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["watch", video_id]:
                await self.video(scrape_item, video_id)
            case ["albums", album_id]:
                await self.album(scrape_item, album_id)
            case ["u", user_id]:
                await self.user_videos(scrape_item, user_id)
            case ["u", user_id, "albums"]:
                await self.user_albums(scrape_item, user_id)
            case _:
                raise ValueError

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["e" | "d", video_id]:
                return url.origin() / "watch" / video_id
            case _:
                return url

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return
        video = await self.api.video(video_id)
        await self._video(scrape_item, video)

    _video_task = auto_task_id(video)

    async def _video(self, scrape_item: ScrapeItem, video: Video) -> None:
        try:
            filename, ext = self.get_filename_and_ext(video.title, assume_ext=".mp4")
        except NoExtensionError:
            filename, ext = self.get_filename_and_ext(video.title + ".mp4")

        if not scrape_item.album_id:
            scrape_item.album_id = video.album_id

        src, m3u8 = video.src, None
        if not src:
            src = await self.api.hls_video(video.id)
            m3u8, _ = await self.request_m3u8(src)

        await self.handle_file(
            src,
            scrape_item,
            video.title,
            ext,
            custom_filename=filename,
            metadata=video,
            thumbnail=video.thumbnail,
            m3u8=m3u8,
        )

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        album = await self.api.album(album_id, sort=scrape_item.url.query.get("sort", "newest"))
        scrape_item.setup_as_album(self.create_title(album.name, album_id), album_id=album_id)

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            for video in album.videos:
                tg.create_task(self._video_task(scrape_item.create_child(video), video.name))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def user_videos(self, scrape_item: ScrapeItem, user_id: str) -> None:
        soup, pages = await aio.peek_next(self.web_pager(scrape_item.url))
        name = css.select_text(soup, "h1")
        scrape_item.setup_as_profile(self.create_title(f"{name} [user]", user_id))

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            async for soup in pages:
                for child in self.iter_children(
                    scrape_item,
                    soup,
                    ".media-section[aria-labelledby='profile-videos-heading'] .media-grid .media-card",
                ):
                    tg.create_task(self._video_task(child, child.url.name))
                    await sleep()

    @error_handling_wrapper
    async def user_albums(self, scrape_item: ScrapeItem, user_id: str) -> None:
        soup = await self.request_soup(self.PRIMARY_URL / "u" / user_id)
        name = css.select_text(soup, "h1")
        scrape_item.setup_as_profile(self.create_title(f"{name} [user]", user_id))

        for child in self.iter_children(
            scrape_item, soup, ".media-section[aria-labelledby='profile-albums-heading'] .album-row .media-card"
        ):
            self.create_task(self.run(child))


@dataclasses.dataclass(slots=True, frozen=True)
class User:
    name: str
    id: str
    url: AbsoluteHttpURL


@dataclasses.dataclass(slots=True, frozen=True)
class Album:
    name: str
    id: str
    videos: tuple[AbsoluteHttpURL, ...]


@dataclasses.dataclass(slots=True, frozen=True)
class Video:
    id: str
    title: str
    uploader: User
    thumbnail: AbsoluteHttpURL
    src: AbsoluteHttpURL | None
    meta: dict[str, str]
    album_id: str | None = None


class ArchveAPI(API):
    async def video(self, video_id: str) -> Video:
        html = await self.request_text(self.PRIMARY_URL / "watch" / video_id)
        return await asyncio.to_thread(_parse_video, html)

    async def album(self, album_id: str, sort: str = "newest") -> Album:
        url = (self.PRIMARY_URL / "albums" / album_id).with_query(sort=sort)
        html = await self.request_text(url)
        return await asyncio.to_thread(_parse_album, html)

    async def hls_video(self, video_id: str) -> AbsoluteHttpURL:
        embed_url = self.PRIMARY_URL / "e" / video_id
        old = None

        def is_obfuscated(var: str) -> bool:
            return var.startswith("_") and "(" in var

        for retry in range(1, 11):
            html = await self.request_text(embed_url.with_query(t=time.time_ns()))
            player = base64.b64decode(b64_pad(extr_text(html, 'playerB64 = "', '";'))).decode("utf8")
            url = extr_text(player, "const videoURL=", ",").strip("'")
            passphase = extr_text(player, "decryptLink(videoURL,", "),").strip("'")
            cred = url, passphase
            if any(map(is_obfuscated, cred)):
                self.log.warning(
                    "Unable to get credentials to decrypt HLS stream of video [%s] (%s)",
                    video_id,
                    f"{url = }, {passphase = }, {retry = }",
                )
                if old == cred:
                    break
                old = cred
                continue

            return self.parse_url(await asyncio.to_thread(_decrypt_cjs, url, passphase))

        raise ScrapeError(422, "Unable to get HLS stream")


def _parse_video(html: str) -> Video:
    soup = css.soup(html)
    meta = css.select(soup, ".watch-meta")
    actions = css.select(soup, ".watch-actions")
    urls = {css.text(tag): ArchveCrawler.parse_url(css.attr(tag, "href")) for tag in css.iselect(actions, "a[href]")}

    user = css.select(meta, "a.media-card__user")
    user_url = ArchveCrawler.parse_url(css.attr(user, "href"))
    album = urls.get("View album")
    thumb = urls["Thumbnail"]

    return Video(
        id=thumb.name,
        title=css.select_text(meta, "h1"),
        uploader=User(name=css.text(user), id=user_url.name, url=user_url),
        thumbnail=thumb,
        src=urls.get("Download"),
        album_id=album.name if album else None,
        meta={css.attr(tag, "title"): css.text(tag) for tag in css.iselect(meta, "span[title][class*='watch-meta__']")},
    )


def _parse_album(html: str) -> Album:
    soup = css.soup(html)
    return Album(
        name=css.select_text(soup, "h1"),
        id=css.select(soup, "form.album-sort", "action").rpartition("/")[-1],
        videos=tuple(map(ArchveCrawler.parse_url, css.iselect(soup, ".media-grid a.media-card", "href"))),
    )


def _evp_bytes_to_key(data: bytes, salt: bytes, key_len: int, iv_len: int):
    out = b""
    previous = b""

    while len(out) < key_len + iv_len:
        previous = hashlib.md5(previous + data + salt, usedforsecurity=False).digest()
        out += previous

    return out[:key_len], out[key_len : key_len + iv_len]


def _decrypt_cjs(ciphertext: str, password: str) -> str:
    raw = base64.b64decode(b64_pad(ciphertext))
    if not raw.startswith(b"Salted__"):
        raise ValueError("Unsupported ciphertext: missing Salted__ header")

    encrypted = raw[16:]
    key, iv = _evp_bytes_to_key(password.encode("utf-8"), salt=raw[8:16], key_len=32, iv_len=16)
    return aes_unpad(aes_cbc_decrypt(encrypted, key, iv)).decode("utf-8")
