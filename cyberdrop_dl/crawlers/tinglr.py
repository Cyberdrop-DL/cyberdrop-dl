from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.cache import disk_cached_method
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import LoginError, ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class TinglrCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": "/video/<video_id>",
        "Youtube video": "/yt/<yt_id>",
    }
    DOMAIN: ClassVar[str] = "tinglr"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://tinglr.co")
    YT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://www.youtube.com/watch")

    def __post_init__(self) -> None:
        self.api: TinglrAPI = TinglrAPI.from_crawler(self)

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

        if not video["is_bunny"]:
            raise ScrapeError(422, "Only bunny CDN videos are supported")

        title = video["title"]
        scrape_item.setup_as_album(self.create_title(title, video_id))
        thumb_name = self.create_custom_filename(video_id, ".jpg")

        headers = {"Referer": str(self.PRIMARY_URL.origin())}
        async with aio.non_cancelling_taskgroup() as tg:
            tg.create_task(self.handle_thumb(video.get("thumbnail_url"), thumb_name, scrape_item))
            tg.create_task(self.write_metadata(scrape_item, f"video_{video_id}", video))
            stream = await self.api.bunny_stream(video_id)
            m3u8, info = await self.request_m3u8_playlist(stream, headers=headers, keep_query=True)
            tg.create_task(
                self.handle_file(
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
            )


class TinglrAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://xagsegkooqopnybovcou.supabase.co/rest/v1")
    CLIENT_VERSION: ClassVar[str] = "supabase-js-web/2.105.1"

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

    async def bunny_stream(self, video_id: str) -> AbsoluteHttpURL:
        url = (self.PRIMARY_URL / "api/bunny-video").with_query(stream=video_id)
        resp = await self.request_json(url)
        return self.parse_url(resp["streamUrl"])

    async def video(self, video_id: str) -> dict[str, Any]:
        url = (self.ENTRYPOINT / "videos").with_query(
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
        key = await self.supabase_anon_key()
        return await self.request_json(
            url,
            headers={
                "Accept": "application/vnd.pgrst.object+json",
                "Authorization": f"Bearer {key}",
                "apikey": key,
                "Referer": str(self.PRIMARY_URL),
                "x-client-info": self.CLIENT_VERSION,
            },
        )
