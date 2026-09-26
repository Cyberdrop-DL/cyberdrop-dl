from __future__ import annotations

import dataclasses
import itertools
from typing import TYPE_CHECKING, Any, ClassVar, Final

from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from cyberdrop_dl.url_objects import ScrapeItem


_VIDEO: Final = AbsoluteHttpURL("https://video.beeg.com")
_THUMBS: Final = AbsoluteHttpURL("https://thumbs.externulls.com")
_STORE: Final = AbsoluteHttpURL("https://store.externulls.com")


@HTTPConfig(rate_limit=(4, 1))
class BeegComCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Video": (
            "/-<video_id>",
            "/video/-<video_id>",
        ),
        "Tags / Network / Model": (
            "/<tag>",
            "/<tag_1>+<tag_2>",
        ),
    }
    DOMAIN: ClassVar[str] = "beeg.com"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://beeg.com")

    def __post_init__(self) -> None:
        self.api: BeegAPI = BeegAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [slug] if slug not in {"reacted", "saved", "following"}:
                if slug.startswith("-"):
                    video_id = int(slug.lstrip("-"))
                    await self.video(scrape_item, video_id)
                else:
                    await self.tags(scrape_item, slug)
            case _:
                raise ValueError

    @classmethod
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = super().transform_url(url)
        match url.parts[1:]:
            case ["video", video_id]:
                return url.origin() / _video_slug(video_id)
            case _:
                return url

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: int) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        video = await self.api.video(video_id)
        await self._video(scrape_item, video)

    @error_handling_wrapper
    async def _video_task(self, scrape_item: ScrapeItem, video: Video) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        await self._video(scrape_item, video)

    async def _video(self, scrape_item: ScrapeItem, video: Video) -> None:
        scrape_item.uploaded_at = video.created_at
        m3u8, info = await self.request_m3u8_playlist(video.m3u8, headers={"Referer": str(scrape_item.url)})
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            video.title,
            ext := ".mp4",
            custom_filename=self.create_custom_filename(
                video.title,
                ext,
                file_id=str(video.id),
                resolution=info.resolution,
                video_codec=info.codecs.video,
                audio_codec=info.codecs.audio,
            ),
            m3u8=m3u8,
            thumbnail=video.thumb,
        )

    @error_handling_wrapper
    async def tags(self, scrape_item: ScrapeItem, slug: str) -> None:
        tags = slug.split("+")
        scrape_item.setup_as_album(self.create_title(slug))

        found_videos: bool = False
        async for videos in self.api.tag_videos(*tags):
            for video in videos:
                found_videos = True
                new_item = scrape_item.create_child(self.PRIMARY_URL / _video_slug(video.id))
                self.create_task(self._video_task(new_item, video))
                scrape_item.add_children()

        if not found_videos:
            raise ScrapeError(404)


class BeegAPI(API):
    async def video(self, video_id: int) -> Video:
        resp: dict[str, Any] = await self.request_json(_STORE / f"facts/file/{video_id}")
        return _parse_video(resp)

    async def tag(self, slug: str) -> dict[str, Any]:
        url = (_STORE / "tag").with_query(slug=slug, get_original="true")
        resp = await self.request_json(url)
        return _normalize_tag(resp)

    async def tag_videos(self, *tags: str) -> AsyncGenerator[map[Video]]:
        limit = 48
        url = (_STORE / "tag/videos" / ",".join(tags)).with_query(limit=limit)
        for offset in itertools.count(0, limit):
            resp = await self.request_json(url.update_query(offset=offset))
            yield map(_parse_video, resp)
            if len(resp) < limit:
                break


@dataclasses.dataclass(order=True, frozen=True, slots=True)
class Video:
    id: int
    title: str
    created_at: int
    thumb: AbsoluteHttpURL
    m3u8: AbsoluteHttpURL
    tags: tuple[dict[str, Any], ...]


def _video_slug(video_id: str | int) -> str:
    return f"-{str(video_id).lstrip('-').zfill(16)}"


def _normalize_tag(resp: Mapping[str, Any]) -> dict[str, Any]:
    tag = _filter_by_prefix(resp, "tg_")
    tag["description"] = next((d["td_value"] for d in resp["data"] if d["td_tag"] == tag["id"]), None)
    tag["links"] = [_normalize_link(link) for link in resp.get("links", ())]
    tag["mother_brand"] = _normalize_tag(mb) if (mb := resp.get("mother_brand")) else None
    return tag


def _normalize_link(data: Mapping[str, Any]) -> dict[str, Any]:
    link = _filter_by_prefix(data, "tk_")
    link["type"] = _filter_by_prefix(data["type"], "tt_")
    return link


def _filter_by_prefix(data: Mapping[str, Any], prefix: str) -> dict[str, Any]:
    return {k.removeprefix(prefix): v for k, v in data.items() if k == "id" or k.startswith(prefix)}


def _parse_video(video: dict[str, Any]) -> Video:
    facts: dict[str, Any] = min(video["fc_facts"], key=lambda x: int(x["id"]))
    file: dict[str, Any] = video["file"]
    thumb: int = next(iter(facts["fc_thumbs"]), 0)
    video_id = int(file["id"])

    return Video(
        id=video_id,
        title=next(d for d in file["data"] if d.get("cd_file") == video_id)["cd_value"],
        created_at=int(Crawler.parse_iso_date(facts["fc_created"])),
        thumb=_THUMBS / f"videos/{video_id}/{thumb}.webp",
        m3u8=_VIDEO / file["hls_resources"]["fl_cdn_multi"],
        tags=tuple(map(_normalize_tag, video.get("tags", ()))),
    )
