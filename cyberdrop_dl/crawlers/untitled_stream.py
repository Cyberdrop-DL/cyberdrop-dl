from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING, Any, ClassVar, Self

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.network.http import HTTPConfig
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.dataclass import deserialize, struct
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.urls import parse_http_url

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import ScrapeItem


class UntitledStreamCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Project": "/library/project/<slug>",
    }
    DOMAIN: ClassVar[str] = "untitled.stream"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://untitled.stream")
    FOLDER_DOMAIN: ClassVar[str] = "Untitled.Stream"

    def __post_init__(self) -> None:
        self.api: UntitledStreamAPI = UntitledStreamAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["library", "project", slug]:
                await self.project(scrape_item, slug)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def project(self, scrape_item: ScrapeItem, slug: str) -> None:
        project, tracks = await self.api.project(slug)
        scrape_item.setup_as_album(self.create_title(project.title, project.slug), album_id=slug)

        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            tg.create_task(self.write_metadata(scrape_item, f"project_{slug}", project))
            tg.create_task(self.handle_thumb(project.artwork_signed_url, project.title + ".jpg", scrape_item, "cover"))
            for track in tracks:
                tg.create_task(self.track(scrape_item, project, track))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def track(self, scrape_item: ScrapeItem, project: Project, track: Track) -> None:
        src = next((s for s in track.sources if s.bucket == "private-audio"), track.sources[0])
        scrape_item.uploaded_at = track.time_created
        name = " - ".join((project.artist_name or project.username, track.title))
        ext = self.get_filename_and_ext(src.url.name).suffix
        await self.handle_file(
            src.url,
            scrape_item,
            name,
            ext,
            custom_filename=self.create_custom_filename(name, ext),
            debrid_link=lambda: self.api.sign(src.bucket, src.path),
            metadata=track,
        )


@struct
class Project:
    title: str
    slug: str
    artist_name: str
    username: str
    artwork_signed_url: str


@struct
class Track:
    id: str
    slug: str
    title: str
    file_type: str
    time_created: float
    sources: tuple[Source]

    @classmethod
    def parse(cls, track: dict[str, Any]) -> Self:
        def sources():
            urls = filter(None, map(track.get, ("file_url", "audio_url", "audio_fallback_url")))
            for url in map(parse_http_url, urls):
                if location := url.path.partition("/object/")[-1]:
                    bucket, _, path = location.partition("/")
                    assert path
                    yield Source(bucket=bucket, path=path, url=url)

        return deserialize(cls, track, sources=tuple(sources()))


@struct
class Source:
    bucket: str
    path: str
    url: AbsoluteHttpURL


@HTTPConfig(headers={"Accept": "application/json"})
class UntitledStreamAPI(API):
    async def sign(self, bucket: str, path: str) -> AbsoluteHttpURL:
        url = (
            self.PRIMARY_URL
            / "api/storage/buckets"
            / bucket
            / "objects"
            / urllib.parse.quote(path, safe="")
            / "signedUrl"
        ).with_query(durationInSeconds=10_800, cacheBufferInSeconds=600)
        resp = await self.request_json(url)
        return self.parse_url(resp["url"])

    async def project(self, slug: str) -> tuple[Project, tuple[Track, ...]]:
        url = (self.PRIMARY_URL / "library/project" / slug).with_query("_data")
        resp = await self.request_json(url)
        project = resp["project"]["project"]
        tracks = resp["project"].get("tracks") or []

        return deserialize(Project, project), tuple(map(Track.parse, tracks))
