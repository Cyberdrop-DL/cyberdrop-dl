from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, override

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedDomains, SupportedPaths, auto_task_id
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import Deduper, traversal, unique
from cyberdrop_dl.utils.dataclass import deserialize, struct
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.urls import parse_http_url, remove_query_params

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.url_objects import ScrapeItem


@Crawler.db_path_builder("path_qs")
class IdagioCrawler(Crawler):
    SUPPORTED_DOMAINS: ClassVar[SupportedDomains] = ("app.idagio.com",)
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Track": "/<lang>/recordings/<rid>?trackId=<track_id>",
        "Recording": "/<lang>/recordings/<rid>",
        "Album": "/<lang>/albums/<slug>",
        "Playlist": "/<lang>/playlists/<slug>",
        "Personal playlist": "/<lang>/playlists/personal/<id>",
    }
    DOMAIN: ClassVar[str] = "idagio"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://app.idagio.com")

    def __post_init__(self) -> None:
        self.api: IdagioAPI = IdagioAPI.from_crawler(self)
        self.seen_records: Deduper[str] = Deduper()

    @classmethod
    @override
    def transform_url(cls, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        url = remove_query_params(super().transform_url(url), keep=("trackId",))
        match url.parts[1:]:
            case [_lang, "recordings" | "works" | "albums" as kind, rid]:
                return (cls.PRIMARY_URL / kind / rid).with_query(url.query)
            case _:
                return url

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        url = scrape_item.url
        match url.parts[1:]:
            case ["recordings", rid]:
                if track_id := url.query.get("trackId"):
                    await self.track(scrape_item, track_id)
                else:
                    await self.recording(scrape_item, rid)
            case ["albums", slug]:
                await self.playlist(scrape_item, slug, "album")
            case ["playlists", slug]:
                await self.playlist(scrape_item, slug, "playlist")
            case ["playlists", "personal", pid]:
                await self.playlist(scrape_item, pid, "personal")
            case _:
                raise ValueError

    @override
    async def write_metadata(self, scrape_item: ScrapeItem, name: str, metadata: object) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        if name in self.seen_records:
            return
        await super().write_metadata(scrape_item, name, metadata)

    @error_handling_wrapper
    async def playlist(
        self, scrape_item: ScrapeItem, slug: str, kind: Literal["album", "playlist", "personal"]
    ) -> None:
        if kind == "album":
            play, tracks = await self.api.album(slug)
            name = play.slug
        elif kind == "personal":
            play, tracks = await self.api.personal_playlist(slug)
            name = play.id
        else:
            play, tracks = await self.api.playlist(slug)
            name = play.slug or play.id

        scrape_item.setup_as_album(self.create_title(f"{play.title} [{kind}]"))
        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            tg.create_task(self.write_metadata(scrape_item, f"{kind}_{name}", play))
            tg.create_task(self.handle_thumb(play.cover, f"{name}.jpg", scrape_item, "cover"))
            for track, recording in tracks:
                url = (self.PRIMARY_URL / f"recordings/{recording.id}").with_query(trackId=track.id)
                tg.create_task(self._track_task(scrape_item.create_child(url), track, recording))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def recording(self, scrape_item: ScrapeItem, recording_id: str) -> None:
        scrape_item.setup_as_album("")
        track_ids, completed = await aio.gather(
            self.api.recording_tracks(recording_id), self.get_completed_by_album(recording_id)
        )
        sleep = aio.periodic_sleep(10)
        async with aio.non_cancelling_taskgroup() as tg:
            for track, recording in await self.api.tracks(track_ids):
                url = (self.PRIMARY_URL / f"recordings/{recording.id}").with_query(trackId=track.id)
                if url in completed:
                    continue

                tg.create_task(self._track_task(scrape_item.create_child(url), track, recording))
                scrape_item.add_children()
                await sleep()

    @error_handling_wrapper
    async def track(self, scrape_item: ScrapeItem, track_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        track, recording = await self.api.track(track_id)
        await self._track(scrape_item, track, recording)

    @error_handling_wrapper
    async def _track(self, scrape_item: ScrapeItem, track: Track, recording: Recording) -> None:
        title = self.create_title(track.piece.work.title, str(recording.id))
        scrape_item.setup_as_album(title, album_id=str(recording.id))
        self.create_eager_task(self.write_metadata(scrape_item, f"recording_{recording.id}", recording))
        name = " - ".join((", ".join(recording.artists), track.piece.title))
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            name,
            ext := ".mp3",
            custom_filename=self.create_custom_filename(name, ext),
            debrid_link=lambda: self.api.content(track.id),
            uploaded_at=recording.created_at,
            metadata=track,
        )

    _track_task = auto_task_id(_track)


type TrackResp = tuple[Track, Recording]


@struct
class Work:
    id: int
    title: str
    composer: str | None
    authors: tuple[str, ...]
    compositionYear: str | None = None  # noqa: N815

    @classmethod
    def parse(cls, work: dict[str, Any]) -> Self:
        return deserialize(
            cls,
            work,
            composer=next(_find_people(work, "composer"), None),
            authors=tuple(_find_people(work, "authors")),
        )


@struct
class Recording:
    id: int
    created_at: int
    conductor: str | None
    ensembles: tuple[str, ...]
    soloists: tuple[str, ...]
    albums: tuple[str, ...]
    summary: str
    artists: tuple[str, ...] = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        artists = unique(filter(None, (self.conductor, *self.ensembles, *self.soloists)))
        object.__setattr__(self, "artists", tuple(artists))

    @classmethod
    def parse(cls, record: dict[str, Any]) -> Self:
        return deserialize(
            cls,
            record,
            albums=tuple(record.get("albums") or ()),
            created_at=record["created_at"] // 1000,
            conductor=next(_find_people(record, "conductor"), None),
            **{name: tuple(_find_people(record, name)) for name in ("ensembles", "soloists")},
        )


@struct
class Piece:
    id: int
    title: str
    work: Work

    parse = classmethod(deserialize)


@struct
class Track:
    id: int
    duration: int
    piece: Piece
    parse = classmethod(deserialize)


@struct
class Album:
    slug: str
    uuid: str
    title: str
    cover: AbsoluteHttpURL
    description: str | None
    lastModified: str  # noqa: N815
    artists: tuple[str, ...]

    @classmethod
    def parse(cls, album: dict[str, Any]) -> Self:
        return deserialize(
            cls,
            album,
            artists=tuple(unique(_find_people(album, "participants"))),
            cover=parse_http_url(album["imageUrl"]),
        )


@struct
class Playlist:
    id: str
    title: str
    cover: AbsoluteHttpURL | None
    slug: str | None = None
    description: str | None = None

    @classmethod
    def parse(cls, play: dict[str, Any]) -> Self:
        cover = play.get("imageUrl") or play.get("image_url") or None
        return deserialize(cls, play, cover=cover and parse_http_url(cover))


class IdagioAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.idagio.com")

    async def content(self, track_id: str | int, *, quality: Literal["mp3", "mp3-320"] = "mp3-320") -> AbsoluteHttpURL:
        url = (self.ENTRYPOINT / f"v1.8/content/track/{track_id}").with_query(
            quality=10 if quality == "mp3-320" else 0,
            format=2,
            client_type="web-4",
        )
        resp = await self.request_json(url)
        return self.parse_url(resp["url"])

    async def track(self, track_id: str) -> TrackResp:
        url = self.ENTRYPOINT / "v2.0/metadata/tracks" / track_id
        resp = await self.request_json(url)
        if (error := resp.get("error_code")) == "idagio.error.blocked.location":
            raise ScrapeError(403, error)

        return _parse_track_resp(resp["result"])

    async def recording_tracks(self, recording_id: str) -> list[str]:
        url = self.ENTRYPOINT / "v2.0/metadata/recordings" / recording_id
        resp = await self.request_json(url)
        return [t["id"] for t in resp["result"].get("tracks", ())]

    async def tracks(self, track_ids: list[str] | tuple[str, ...]) -> list[TrackResp]:
        if not track_ids:
            return []

        url = self.ENTRYPOINT / "v2.0/metadata/tracks/bulk"
        resp = await self.request_json(url, "POST", json={"ids": track_ids})
        return [_parse_track_resp(r) for r in resp["results"]]

    async def album(self, slug: str) -> tuple[Album, list[TrackResp]]:
        url = self.ENTRYPOINT / "v2.0/metadata/albums" / slug
        data, tracks = await self._playlist(url)
        return Album.parse(data), tracks

    async def playlist(self, slug: str) -> tuple[Playlist, list[TrackResp]]:
        url = self.ENTRYPOINT / "v2.0/playlists" / slug
        data, tracks = await self._playlist(url)
        return Playlist.parse(data), tracks

    async def personal_playlist(self, playlist_id: str) -> tuple[Playlist, list[TrackResp]]:
        url = self.ENTRYPOINT / "v1.0/personal-playlists" / playlist_id
        data, tracks = await self._playlist(url)
        return Playlist.parse(data), tracks

    async def _playlist(self, url: AbsoluteHttpURL) -> tuple[dict[str, Any], list[TrackResp]]:
        resp = await self.request_json(url)
        data = resp["result"]
        tracks = [_parse_track_resp(r) for r in data.get("tracks", ())]
        return data, tracks


def _parse_track_resp(result: dict[str, Any]) -> tuple[Track, Recording]:
    piece = Piece.parse(result["piece"], work=Work.parse(result["piece"]["workpart"]["work"]))
    return Track.parse(result, piece=piece), Recording.parse(result["recording"])


def _find_people(data: dict[str, Any], name: str) -> Generator[str]:
    for _, person in traversal.find_objs(data.get(name) or {}, "name"):
        if name := person["name"]:
            yield name
