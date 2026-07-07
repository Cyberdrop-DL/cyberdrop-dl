# ruff: noqa: N815
from __future__ import annotations

import dataclasses
import itertools
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Crawler, SupportedPaths
from cyberdrop_dl.mediaprops import Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import nuxt
from cyberdrop_dl.utils.dataclass import DictDataclass
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator, Iterable
    from typing import Any

    from cyberdrop_dl.url_objects import ScrapeItem


PRIMARY_URL = AbsoluteHttpURL("https://pmvhaven.com")


@dataclasses.dataclass(slots=True)
class Video(DictDataclass):
    # TODO: parse and download previews and thumbnails
    id: str
    title: str
    videoUrl: str
    uploadDate: str
    width: int
    height: int

    hlsMasterPlaylistUrl: str | None = None

    @classmethod
    def filter_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        data["id"] = data["_id"]
        return super(Video, cls).filter_dict(data)

    @property
    def web_url(self) -> AbsoluteHttpURL:
        # The title does not matter, the website parses the id from the url and redirects to the correct video
        return PRIMARY_URL / f"video/{self.title.lower()}_{self.id}"


class PMVHavenCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Playlist": "/playlists/...",
        "Search results": "/search/...",
        "Users": (
            "/profile/...",
            "/users/...",
        ),
        "Video": "/video/...",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = PRIMARY_URL
    DOMAIN: ClassVar[str] = "pmvhaven"
    FOLDER_DOMAIN: ClassVar[str] = "PMVHaven"

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video", slug] if video_id := slug.rsplit("_", 1)[-1]:
                return await self.video(scrape_item, video_id)
            case ["search"] if query := scrape_item.url.query.get("q"):
                return await self.search(scrape_item, query)
            case ["users" | "profile", _]:
                return await self.profile(scrape_item)
            case ["playlists", playlist_id]:
                return await self.playlist(scrape_item, playlist_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def profile(self, scrape_item: ScrapeItem) -> None:
        soup = await self.request_soup(scrape_item.url)
        data = nuxt.extract(soup)
        username: str = nuxt.find(data, "username")["username"]
        title = self.create_title(f"{username} [user]")
        scrape_item.setup_as_profile(title)

        for video in _parse_videos(nuxt.ifind(data, "videoUrl", "title")):
            await self._video(scrape_item.copy(), video)
            scrape_item.add_children()

    @error_handling_wrapper
    async def playlist(self, scrape_item: ScrapeItem, playlist_id: str) -> None:
        # TODO: use playlist as album_id to skip downloads faster
        api_url = self.PRIMARY_URL / "api/playlists" / playlist_id
        data, pages = await aio.peek_first(self._api_pager(api_url))
        title = self.create_title(f"{data['name']} [playlist]")
        scrape_item.setup_as_album(title)

        async for data in pages:
            for video in _parse_videos(data["videoDetails"]):
                await self._video(scrape_item.copy(), video)
                scrape_item.add_children()

    async def _api_pager(self, api_url: AbsoluteHttpURL, init_page: int = 1) -> AsyncGenerator[Any]:
        for page in itertools.count(init_page):
            resp: dict[str, Any] = await self.request_json(api_url.update_query(limit=100, page=page))
            yield resp["data"]
            if not resp["pagination"]["hasMore"]:
                break

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        title = self.create_title(f"{query} [search]")
        scrape_item.setup_as_profile(title)
        api_url = (self.PRIMARY_URL / "api/videos/search").with_query(q=query)
        data: list[dict[str, Any]]
        async for data in self._api_pager(api_url):
            for video in _parse_videos(data):
                await self._video(scrape_item.copy(), video)
                scrape_item.add_children()

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        api_url = self.PRIMARY_URL / "api/videos" / video_id
        data = (await self.request_json(api_url))["data"]
        video = Video.from_dict(data)
        await self._video(scrape_item, video)

    @error_handling_wrapper
    async def _video(self, scrape_item: ScrapeItem, video: Video) -> None:
        scrape_item.url = video.web_url
        scrape_item.uploaded_at = self.parse_iso_date(video.uploadDate)
        link = self.parse_url(video.videoUrl)
        filename, ext = self.get_filename_and_ext(link.name, assume_ext=".mp4")
        custom_filename = self.create_custom_filename(
            video.title,
            ext,
            file_id=video.id,
            resolution=Resolution(video.width, video.height),
        )
        await self.handle_file(link, scrape_item, filename, ext, custom_filename=custom_filename, metadata=video)


def _parse_videos(videos: Iterable[dict[str, Any]]) -> Generator[Video]:
    ids: set[str] = set()
    for data in videos:
        if data["_id"] not in ids:
            ids.add(data["_id"])
            yield Video.from_dict(data)
