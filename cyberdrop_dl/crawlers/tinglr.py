from __future__ import annotations

import dataclasses
import functools
import re
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.cache import disk_cached_method
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import LoginError, ScrapeError
from cyberdrop_dl.network.http import HTTPConfig
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.json import JSONWebToken

if TYPE_CHECKING:
    from cyberdrop_dl.network.response import AbstractResponse
    from cyberdrop_dl.url_objects import ScrapeItem


class TinglrCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/video/<video_id>",
        "Youtube video": "/yt/<yt_id>",
    }
    DOMAIN: ClassVar[str] = "tinglr"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://tinglr.co")
    YT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.youtube.com/watch")

    async def __async_post_init__(self) -> None:
        self.api: TinglrAPI = TinglrAPI.from_crawler(self)
        if jwt := self.config.auth.tinglr.api_key:
            self.api.auth_key = jwt

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["yt", video_id]:
                await self.youtube(scrape_item, video_id)
            case ["video", video_id]:
                await self.video(scrape_item, video_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def youtube(self, scrape_item: ScrapeItem, video_id: str) -> None:
        with scrape_item.track_changes:
            scrape_item.url = self.YT.update_query(v=video_id)
        self.handle_embed(scrape_item)

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        video = await self.api.video(video_id)
        title = video["title"]
        scrape_item.setup_as_album(self.create_title(title, video_id))
        thumb_name = self.create_custom_filename(video_id, ".jpg")

        headers = {"Referer": str(self.PRIMARY_URL.origin())}
        if video["nsfw"]:
            thumb = self.api.nsfw_thumb(video_id)
            thumb_suffix = "_blur_thumb"
        else:
            thumb = video.get("thumbnail_url")
            thumb_suffix = "_thumb"

        self.create_eager_task(self.handle_thumb(thumb, thumb_name, scrape_item, thumb_suffix))
        self.create_eager_task(self.write_metadata(scrape_item, f"video_{video_id}", video))
        if not video["is_bunny"]:
            raise ScrapeError(422, "Only bunny CDN videos are supported")

        stream = await self.api.bunny_stream(video_id)
        m3u8, info = await self.request_m3u8_playlist(stream, headers=headers, keep_query=True)
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            title,
            ext := ".mp4",
            m3u8=m3u8,
            custom_filename=self.create_custom_filename(
                title, ext, resolution=info and info.resolution, file_id=video_id
            ),
            metadata=video,
            headers=headers,
        )


def _json_check(data: Any, resp: AbstractResponse[Any], *, jwt: JSONWebToken | None = None) -> None:
    if type(data) is not dict:
        return

    errors = tuple(map(data.get, ("error", "code", "message")))
    if errors[0] == "Purchase required":
        raise ScrapeError(HTTPStatus.PAYMENT_REQUIRED, errors[0])

    if resp.status == 406:
        if jwt is None:
            msg = "NSFW videos require a logged in account. Provide a JWT in the config"
        elif jwt.is_expired(300):
            msg = "Account JWT has expired"
        else:
            msg = "NSFW videos are disabled on your account"
        raise ScrapeError(HTTPStatus.UNAUTHORIZED, msg)

    raise ScrapeError(resp.status, " - ".join(filter(None, errors)))


@HTTPConfig(json_check=_json_check)
class TinglrAPI(API):
    SUPA: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://xagsegkooqopnybovcou.supabase.co/rest/v1")
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://tinglr.co/api")
    CLIENT_VERSION: ClassVar[str] = "supabase-js-web/2.105.1"
    _jwt: JSONWebToken | None = None

    def nsfw_thumb(self, video_id: str) -> AbsoluteHttpURL:
        # TODO: Implement proper sign workflow. These are blurred thumbnails
        return (self.ENTRYPOINT / "nsfw-thumb").update_query(v=video_id)

    @property
    def auth_key(self) -> str | None:
        if self._jwt is None:
            return None
        if self._jwt.is_expired(300):
            raise ScrapeError(403, "API key has expired")
        return self._jwt.encoded

    @auth_key.setter
    def auth_key(self, jwt: str | None) -> None:
        if jwt:
            self._jwt = JSONWebToken.decode(jwt)
            if self._jwt.payload.get("is_anonymous"):
                raise ScrapeError(
                    HTTPStatus.UNAUTHORIZED, "Please provide a JWT of a logged in account (not anonymous)"
                )
            json_check = functools.partial(_json_check, jwt=self._jwt)
        else:
            self._jwt = None
            json_check = _json_check
        self.__http_ctx__ = dataclasses.replace(self.__http_ctx__, json_check=json_check)

    @disk_cached_method(ttl=86_400 * 30)
    async def supabase_anon_key(self) -> str:
        async with self.request(self.PRIMARY_URL) as resp:
            soup = await resp.soup(parse_only="script")

        sources = tuple(
            url
            for url in map(self.parse_url, css.iselect(soup, "script[src]", "src"))
            if url.host == self.PRIMARY_URL.host and url.suffix == ".js" and url.name.startswith("index-")
        )
        pattern = r'VITE_SUPABASE_ANON_KEY\s*:\s*"([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*)"'
        for script_src in sources:
            try:
                script = await self.request_text(script_src)
            except Exception:
                self.log.exception("Unable to get supabase API key from %s", script_src)
            else:
                if m := re.search(pattern, script):
                    self.log.debug("Found new supabase API key in %s", script_src)
                    return m[1]

        raise LoginError("Unable to get a valid supabase API key ")

    async def auth_headers(self) -> dict[str, str]:
        key = self.auth_key or await self.supabase_anon_key()
        return {"Authorization": f"Bearer {key}"}

    async def bunny_stream(self, video_id: str) -> AbsoluteHttpURL:
        url = (self.ENTRYPOINT / "bunny-video").with_query(stream=video_id)
        resp = await self.request_json(url, headers=await self.auth_headers())
        return self.parse_url(resp["streamUrl"])

    async def video(self, video_id: str) -> dict[str, Any]:
        url = (self.SUPA / "videos").with_query(
            id=f"eq.{video_id}",
            select=",".join(
                (
                    "id",
                    "creator_id",
                    "title",
                    "description",
                    "thumbnail_url",
                    "duration",
                    "views",
                    "likes",
                    "category",
                    "exclusive",
                    "tier_id",
                    "tags",
                    "created_at",
                    "nsfw",
                    "scheduled_at",
                    "chapters",
                    "price_cents",
                    "nsfw_locked",
                    "reviewed",
                    "has_video",
                    "is_bunny",
                    "allowed_tier_ids",
                )
            ),
        )

        return await self.request_json(
            url,
            headers={
                "Accept": "application/vnd.pgrst.object+json",
                "apikey": await self.supabase_anon_key(),
                "Referer": str(self.PRIMARY_URL),
                "x-client-info": self.CLIENT_VERSION,
                **(await self.auth_headers()),
            },
        )
