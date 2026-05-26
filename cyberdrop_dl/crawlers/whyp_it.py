from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar

from cyberdrop_dl.crawlers.crawler import API, Crawler, RateLimit, SupportedPaths
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import deserialize, error_handling_wrapper, parse_url

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterable

    from cyberdrop_dl.url_objects import ScrapeItem


class WhypItCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Audio": "/tracks/<id>/...",
        "User": "/users/<id>/<name>",
        "Collection": "/collections/<collection_id>/<name>",
    }

    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://whyp.it")
    DOMAIN: ClassVar[str] = PRIMARY_URL.host
    _RATE_LIMIT: ClassVar[RateLimit] = 5, 1

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["tracks", track_id, *_]:
                return await self.track(scrape_item, track_id)
            case ["users", user_id, _]:
                return await self.user(scrape_item, user_id)
            case ["collections", collection_id, _]:
                return await self.collection(scrape_item, collection_id)
            case _:
                raise ValueError

    def __post_init__(self) -> None:
        self.api: WhypItAPI = WhypItAPI(self)

    @error_handling_wrapper
    async def collection(self, scrape_item: ScrapeItem, collection_id: str) -> None:
        collection = await self.api.collection(collection_id)
        scrape_item.setup_as_profile(self.create_title(collection.user))
        scrape_item.add_to_parent_title(self.create_title(collection.title, collection_id))
        await self.write_metadata(scrape_item, f"collection {collection_id}", collection.metadata)
        async for tracks in self.api.collection_tracks(collection_id, collection.token):
            self._iter_tracks(scrape_item, tracks)

    @error_handling_wrapper
    async def user(self, scrape_item: ScrapeItem, user_id: str) -> None:
        title: str = ""
        async for tracks in self.api.user_tracks(user_id):
            if not title:
                tracks = tuple(tracks)
                title = self.create_title(tracks[0].user)
                scrape_item.setup_as_profile(title)

            self._iter_tracks(scrape_item, tracks)

    def _iter_tracks(self, scrape_item: ScrapeItem, tracks: Iterable[Track]) -> None:
        for track in tracks:
            new_item = scrape_item.create_child(track.url)
            self.create_task(self._track(new_item, track))
            scrape_item.add_children()

    @error_handling_wrapper
    async def track(self, scrape_item: ScrapeItem, track_id: str) -> None:
        if await self.check_complete_from_referer(scrape_item):
            return

        track = await self.api.track(track_id, token=scrape_item.url.query.get("token"))
        scrape_item.setup_as_profile(self.create_title(track.user))
        await self._track(scrape_item, track)

    @error_handling_wrapper
    async def _track(self, scrape_item: ScrapeItem, track: Track) -> None:
        scrape_item.uploaded_at = self.parse_iso_date(track.created_at)
        _, ext = self.get_filename_and_ext(track.src.name)
        filename = self.create_custom_filename(track.title, ext, file_id=str(track.id))
        await self.handle_file(
            track.src,
            scrape_item,
            track.title,
            ext,
            custom_filename=filename,
            metadata=track.metadata,
        )


@dataclasses.dataclass(slots=True)
class Track:
    id: int
    title: str
    src: AbsoluteHttpURL
    user: str
    public: bool
    token: str
    metadata: dict[str, Any]
    created_at: str

    @property
    def url(self) -> AbsoluteHttpURL:
        url = WhypItCrawler.PRIMARY_URL / f"tracks/{self.id}"
        if not self.public:
            url = url.with_query(token=self.token)
        return url


@dataclasses.dataclass(slots=True)
class Collection:
    id: int
    title: str
    token: str
    user: str
    metadata: dict[str, Any]


class WhypItAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.whyp.it/api")

    async def track(self, track_id: str, token: str | None) -> Track:
        api_url = self.ENTRYPOINT / "tracks" / track_id
        if token:
            api_url = api_url.with_query(token=token)
        track: dict[str, Any] = (await self.request_json(api_url))["track"]
        return _parse_track(track)

    async def collection(self, collection_id: str) -> Collection:
        api_url = self.ENTRYPOINT / "collections" / collection_id
        collection: dict[str, Any] = (await self.request_json(api_url))["collection"]
        return _parse_collection(collection)

    def user_tracks(self, user_id: str) -> AsyncGenerator[map[Track]]:
        api_url = self.ENTRYPOINT / "users" / user_id / "tracks"
        return self._pager(api_url)

    def collection_tracks(self, collection_id: str, token: str | None) -> AsyncGenerator[map[Track]]:
        api_url = self.ENTRYPOINT / "collections" / collection_id / "tracks"
        if token:
            api_url = api_url.with_query(token=token)
        return self._pager(api_url)

    async def _pager(self, api_url: AbsoluteHttpURL) -> AsyncGenerator[map[Track]]:
        while True:
            resp = await self.request_json(api_url)
            yield map(_parse_track, resp["tracks"])
            cursor = resp.get("next_cursor")
            if not cursor:
                break
            api_url = api_url.with_query(cursor=cursor)


def _parse_track(track: dict[str, Any]) -> Track:
    return deserialize(
        Track,
        track,
        user=track["user"]["username"],
        metadata=track,
        created_at=track.get("created_at") or track["pivot_created_at"],
        src=parse_url(track.get("lossless_url") or track["lossy_url"]),
    )


def _parse_collection(collection: dict[str, Any]) -> Collection:
    return deserialize(Collection, collection, metadata=collection, user=collection["user"]["username"])
