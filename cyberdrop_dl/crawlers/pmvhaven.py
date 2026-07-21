# ruff: noqa: N815
from __future__ import annotations

import dataclasses
import itertools
import operator
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.mediaprops import Resolution
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import nuxt, parse_url, unique
from cyberdrop_dl.utils.dataclass import Deserializer
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterable, Iterable
    from typing import Any

    from cyberdrop_dl.url_objects import ScrapeItem


class PMVHavenCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Playlist": "/playlists/<playlist_id>",
        "Search results": "/search?q=<query>",
        "Users": (
            "/profile/<user_id>",
            "/users/<user_id>",
        ),
        "Video": "/video/<video_name>_<video_id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://pmvhaven.com")
    DOMAIN: ClassVar[str] = "pmvhaven"
    FOLDER_DOMAIN: ClassVar[str] = "PMVHaven"

    def __post_init__(self) -> None:
        self.api: PMVAPI = PMVAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["video", slug] if video_id := slug.rsplit("_", 1)[-1]:
                return await self.video(scrape_item, video_id)
            case ["search"] if query := scrape_item.url.query.get("q"):
                return await self.search(scrape_item, query)
            case ["users" | "profile", user_id]:
                return await self.profile(scrape_item, user_id)
            case ["playlists", playlist_id]:
                return await self.playlist(scrape_item, playlist_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def profile(self, scrape_item: ScrapeItem, user_id: str) -> None:
        username, videos = await self.api.profile(user_id)
        scrape_item.setup_as_profile(self.create_title(f"{username} [user]"))
        self._iter_videos(scrape_item, videos)

    @error_handling_wrapper
    async def playlist(self, scrape_item: ScrapeItem, playlist_id: str) -> None:
        # TODO: use playlist as album_id to skip downloads faster
        playlist, video_pages = await self.api.playlist(playlist_id)
        title = self.create_title(f"{playlist.name} [playlist]")
        scrape_item.setup_as_album(title)
        await self._playlist(scrape_item, playlist)
        video_ids = await self._iter_video_pages(scrape_item, video_pages)
        missing_videos = set(playlist.videos) - video_ids
        if missing_videos:
            self.log.warning(
                "Playlist %s reports %s videos but only %s video were returned. The following videos have been removed: %s",
                scrape_item.url,
                len(playlist.videos),
                len(video_ids),
                sorted(missing_videos),
            )

    async def _playlist(self, scrape_item: ScrapeItem, playlist: Playlist) -> None:
        self.create_eager_task(self.write_metadata(scrape_item, playlist.id, playlist))
        with self.catch_errors(playlist.thumbnail):
            _, ext = self.get_filename_and_ext(playlist.thumbnail.name)
            filename = self.create_custom_filename(playlist.name, ext)
            await self.handle_file(
                playlist.thumbnail,
                scrape_item,
                playlist.thumbnail.name,
                ext,
                frag="thumbnail",
                custom_filename=filename,
            )

    async def _iter_video_pages(self, scrape_item: ScrapeItem, video_pages: AsyncIterable[Iterable[Video]]) -> set[str]:
        seen: set[str] = set()
        async for videos in video_pages:
            seen.update(self._iter_videos(scrape_item, videos))
        return seen

    def _iter_videos(self, scrape_item: ScrapeItem, videos: Iterable[Video]) -> set[str]:
        seen: set[str] = set()
        for video in videos:
            seen.add(video.id)
            new_item = scrape_item.copy()
            new_item.url = self.PRIMARY_URL / video.href
            self.create_eager_task(self._video(new_item, video))
            scrape_item.add_children()
        return seen

    @error_handling_wrapper
    async def search(self, scrape_item: ScrapeItem, query: str) -> None:
        title = self.create_title(f"{query} [search]")
        scrape_item.setup_as_profile(title)
        await self._iter_video_pages(scrape_item, self.api.search(query))

    @error_handling_wrapper
    async def video(self, scrape_item: ScrapeItem, video_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item.url):
            return

        video = await self.api.video(video_id)
        await self._video(scrape_item, video)

    @error_handling_wrapper
    async def _video(self, scrape_item: ScrapeItem, video: Video) -> None:
        scrape_item.uploaded_at = self.parse_iso_date(video.uploadDate)
        link = self.parse_url(video.videoUrl)
        filename, ext = self.get_filename_and_ext(link.name, assume_ext=".mp4")
        custom_filename = self.create_custom_filename(
            video.title,
            ext,
            file_id=video.id,
            resolution=Resolution(video.width, video.height) if video.width and video.height else None,
        )
        await self.handle_file(link, scrape_item, filename, ext, custom_filename=custom_filename, metadata=video)


_deserialize = Deserializer(aliases={"id": "_id"}, converters={"thumbnail": parse_url})


@dataclasses.dataclass(slots=True)
class Video:
    # TODO: parse and download previews and thumbnails
    id: str
    title: str
    videoUrl: str
    uploadDate: str
    width: int | None = None
    height: int | None = None

    hlsMasterPlaylistUrl: str | None = None

    @property
    def href(self) -> str:
        # The title does not matter, the website parses the id from the url and redirects to the correct video
        return f"video/{self.title.lower()}_{self.id}"

    parse = classmethod(_deserialize)


@dataclasses.dataclass(slots=True)
class Playlist:
    id: str
    name: str
    description: str
    thumbnail: AbsoluteHttpURL
    createdAt: str
    updatedAt: str
    videos: list[str]


class PMVAPI(API):
    async def video(self, video_id: str) -> Video:
        api_url = self.PRIMARY_URL / "api/videos" / video_id
        data = (await self.request_json(api_url))["data"]
        return Video.parse(data)

    async def search(self, query: str) -> AsyncGenerator[map[Video]]:
        api_url = (self.PRIMARY_URL / "api/videos/search").with_query(q=query)
        data: list[dict[str, Any]]
        async for data in self.pager(api_url):
            yield _parse_videos(data)

    async def playlist(self, playlist_id: str) -> tuple[Playlist, AsyncGenerator[map[Video]]]:
        api_url = self.PRIMARY_URL / "api/playlists" / playlist_id
        data, pages = await aio.peek_first(self.pager(api_url))
        playlist = _deserialize(Playlist, data)

        async def video_pages():
            async for data in pages:
                yield _parse_videos(data["videoDetails"])

        return playlist, video_pages()

    async def pager(self, api_url: AbsoluteHttpURL, init_page: int = 1) -> AsyncGenerator[Any]:
        for page in itertools.count(init_page):
            resp: dict[str, Any] = await self.request_json(api_url.update_query(limit=100, page=page))
            yield resp["data"]
            if not resp["pagination"]["hasMore"]:
                break

    async def profile(self, user_id: str) -> tuple[str, map[Video]]:
        url = self.PRIMARY_URL / "profile" / user_id
        soup = await self.request_soup(url)
        data = nuxt.extract(soup)
        username: str = nuxt.find(data, "username")["username"]
        videos = _parse_videos(nuxt.ifind(data, "videoUrl", "title"))
        return username, videos


def _parse_videos(videos: Iterable[dict[str, Any]]) -> map[Video]:
    return map(Video.parse, unique(videos, operator.itemgetter("_id")))
