from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, ClassVar

from cyberdrop_dl.cache import disk_cached_method
from cyberdrop_dl.crawlers.crawler import API, Crawler, DownloadConfig, SupportedPaths
from cyberdrop_dl.models import type_adapter
from cyberdrop_dl.models.validators import strings
from cyberdrop_dl.url_objects import AbsoluteHttpURL, ScrapeItem
from cyberdrop_dl.utils import dates
from cyberdrop_dl.utils.dataclass import DictDataclass
from cyberdrop_dl.utils.errors import error_handling_wrapper

if TYPE_CHECKING:
    from collections.abc import Generator


@dataclasses.dataclass(slots=True, frozen=True)
class TrackSettings:
    quality: str
    ext: str


@Crawler.db_path_builder("path_qs")
@DownloadConfig(impersonate=True)
class OctaveMusicCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Artist Albums": "/artist/<artist_id>",
        "Artist Top 50 songs": "/artist/<artist_id>/top-songs",
        "Album": "/album/<album_id",
        "Track": "/album/<album_id>?t=<track_id>",
    }
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://music.octavestreaming.com")
    DOMAIN: ClassVar[str] = "music.octavestreaming"
    FOLDER_DOMAIN: ClassVar[str] = "OctaveMusic"

    def __post_init__(self) -> None:
        self.api: OctaveMusicAPI = OctaveMusicAPI.from_crawler(self)
        match self.config.crawlers.octave_music.quality:
            case "lossless":
                quality, ext = "lossless", ".flac"
            case _:
                quality, ext = "320", ".mp3"

        self._audio: TrackSettings = TrackSettings(quality, ext)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case ["artist", artist_id]:
                await self.artist(scrape_item, artist_id)
            case ["album", album_id]:
                if track_id := scrape_item.url.query.get("t"):
                    return await self.track(scrape_item, track_id)
                await self.album(scrape_item, album_id)
            case ["artist", artist_id, "top-songs"]:
                await self.top(scrape_item, artist_id)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def artist(self, scrape_item: ScrapeItem, artist_id: str) -> None:
        resp = await self.api.artist(artist_id)
        scrape_item.setup_as_profile(self.create_title(resp.artist.name, artist_id))

        for album in resp.albums:
            url = self.PRIMARY_URL / "album" / album.id
            self.create_task(self.run(scrape_item.create_child(url)))
            scrape_item.add_children()

    @error_handling_wrapper
    async def top(self, scrape_item: ScrapeItem, artist_id: str) -> None:
        resp = await self.api.artist(artist_id)
        scrape_item.setup_as_profile(self.create_title(resp.artist.name, artist_id))
        for track in resp.top:
            url = (self.PRIMARY_URL / "album" / track.album.id).update_query(t=track.id)
            self.create_eager_task(self.run(scrape_item.create_child(url)))
            scrape_item.add_children()

    @error_handling_wrapper
    async def album(self, scrape_item: ScrapeItem, album_id: str) -> None:
        album = await self.api.album(album_id)
        scrape_item.setup_as_album(self.create_title(album.title, album.id))

        name, ext = self.get_filename_and_ext(album.cover_xl.name)
        await self.handle_file(
            album.cover_xl,
            scrape_item,
            name,
            ext,
            custom_filename=self.create_custom_filename("cover", ext, file_id=album.id),
        )

        for track in album.tracks:
            url = scrape_item.url.update_query(t=track.id)
            new_item = scrape_item.create_child(url)
            self.create_eager_task(self.run(new_item))
            scrape_item.add_children()

    @error_handling_wrapper
    async def track(self, scrape_item: ScrapeItem, track_id: str) -> None:
        if await self.check_complete(scrape_item.url):
            return

        info = await self.api.credits(track_id)
        scrape_item.upload_date = date = dates.parse_iso(info.releaseDate)
        name, _ = strings.safe_format(
            self.config.crawlers.octave_music.filename_format,
            id=info.id,
            track_number=info.trackNumber,
            disk_number=info.diskNumber,
            title=info.title,
            release_date=date,
            ext=self._audio.ext,
            **dict(info.contributors.decompose()),
        )
        filename, ext = self.get_filename_and_ext(name)
        await self.handle_file(
            scrape_item.url,
            scrape_item,
            name,
            ext,
            custom_filename=filename,
            debrid_link=await self.api.audio(track_id, self._audio.quality),
        )


class OctaveMusicAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api.octavestreaming.com/api")

    @disk_cached_method(ttl=7200)
    async def playback_token(self) -> str:
        url = self.ENTRYPOINT / "playback-token"
        resp = await self.request_json(url, impersonate=True)
        return resp["token"]

    async def audio(self, track_id: str, quality: str) -> AbsoluteHttpURL:
        return (self.ENTRYPOINT.origin() / "audio" / quality).with_query(track=track_id, k=await self.playback_token())

    async def artist(self, artist_id: str) -> ArtistResp:
        url = self.ENTRYPOINT / "artist" / artist_id
        text = await self.request_text(url)
        return type_adapter(ArtistResp).validate_json(text)

    async def album(self, album_id: str) -> FullAlbum:
        url = self.ENTRYPOINT / "album" / album_id
        resp = await self.request_json(url)
        return type_adapter(FullAlbum).validate_python(resp["album"])

    async def credits(self, track_id: str) -> Credits:
        url = self.ENTRYPOINT / "track" / track_id / "credits"
        resp = (await self.request_json(url))["credits"]
        contributors: dict[str, list[str]] = {}
        for con in resp["contributors"]:
            contributors.setdefault(con["role"].casefold(), []).extend(con.get("names", ()))

        resp["contributors"] = contributors
        return type_adapter(Credits).validate_python(resp, by_alias=True)


@dataclasses.dataclass(frozen=True, order=True, slots=True)
class Artist:
    id: str
    name: str


@dataclasses.dataclass(frozen=True, order=True, slots=True)
class Track:
    id: str
    album: Album


@dataclasses.dataclass(frozen=True, order=True, slots=True)
class Album:
    id: str
    title: str


@dataclasses.dataclass(frozen=True, order=True, slots=True)
class FullAlbum:
    id: str
    title: str
    cover_xl: AbsoluteHttpURL
    releaseDate: str  # noqa: N815
    tracks: tuple[Track, ...] = ()


@dataclasses.dataclass(frozen=True, order=True, slots=True)
class ArtistResp:
    artist: Artist
    top: tuple[Track, ...]
    albums: tuple[Album, ...]


@dataclasses.dataclass(frozen=True, order=True, slots=True)
class Contributors:
    artist: tuple[str, ...]
    writer: tuple[str, ...] = ()
    composer: tuple[str, ...] = ()

    __iter__ = DictDataclass.__iter__

    def decompose(self) -> Generator[tuple[str, str]]:
        names: tuple[str, ...]
        for role, names in self:
            if names:
                yield role, names[0]
                yield role + "s", ", ".join(names)


@dataclasses.dataclass(frozen=True, order=True, slots=True)
class Credits:
    id: str
    title: str
    releaseDate: str  # noqa: N815
    trackNumber: int  # noqa: N815
    diskNumber: int  # noqa: N815
    contributors: Contributors
