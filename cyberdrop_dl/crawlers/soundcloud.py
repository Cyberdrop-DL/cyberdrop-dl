from __future__ import annotations

import mimetypes
import re
from typing import TYPE_CHECKING, Any, ClassVar, Literal, NotRequired, Required, TypedDict, cast

from cyberdrop_dl.cache import disk_cached_method
from cyberdrop_dl.clients.http import HTTPConfig
from cyberdrop_dl.crawlers.crawler import API, Crawler, SupportedPaths
from cyberdrop_dl.exceptions import DownloadError, LoginError, ScrapeError
from cyberdrop_dl.filepath import get_filename_and_ext
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import css, extr_text, traversal
from cyberdrop_dl.utils.dataclass import struct
from cyberdrop_dl.utils.errors import error_handling_wrapper
from cyberdrop_dl.utils.urls import parse_http_url

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.url_objects import ScrapeItem


@Crawler.db_path_builder("path_frag")
class SoundCloudCrawler(Crawler):
    SUPPORTED_PATHS: ClassVar[SupportedPaths] = {
        "Track": (
            "/<uploader>/<slug>",
            "/<uploader>/<slug>/<secret_token>",
        ),
    }
    DOMAIN: ClassVar[str] = "soundcloud"
    PRIMARY_URL: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://soundcloud.com")

    def __post_init__(self) -> None:
        self.api: SoundCloudAPI = SoundCloudAPI.from_crawler(self)

    async def fetch(self, scrape_item: ScrapeItem) -> None:
        match scrape_item.url.parts[1:]:
            case [_uploader, _slug] | [_uploader, _slug, _]:
                await self.track_by_url(scrape_item)
            case _:
                raise ValueError

    @error_handling_wrapper
    async def track_by_url(self, scrape_item: ScrapeItem) -> None:
        track = await self.api.track_by_url(scrape_item.url)
        await self._track(scrape_item, track)

    async def _track(self, scrape_item: ScrapeItem, track: Track) -> None:
        scrape_item.uploaded_at = self.parse_iso_date(track["created_at"])
        src = m3u8 = None

        if track.get("downloadable") and track.get("has_downloads_left"):
            try:
                src = await self.api.original(track["id"], track["secret_token"])
            except ScrapeError:
                pass

        if src is None:
            src = await self._select_best_format(track)

        if src.url.suffix == ".m3u8":
            m3u8, _ = await self.request_m3u8(src.url)
            m3u8.video.media_type = "audio"

        name = " - ".join(filter(None, (track["artist"], track["title"])))
        url = self.parse_url(track["permalink_url"]).with_fragment(src.id)
        await self.handle_file(
            url,
            scrape_item,
            name,
            src.ext,
            m3u8=m3u8,
            custom_filename=self.create_custom_filename(name, src.ext, file_id=str(track["id"]), video_codec=src.id),
            thumbnail=track["artwork_url"],
            metadata=track,
        )

    async def _select_best_format(self, track: Track) -> AudioSource:
        formats = sorted((f for f in track["formats"] if not f.is_preview), key=Format.score, reverse=True)
        if not formats:
            raise ScrapeError(422, "Track does not have any non preview formats")

        for fmt in formats:
            try:
                url = await self.api.stream(fmt.url)
            except DownloadError as e:
                if e.status != 404:
                    raise
                self.log.error("Format '%s' from track %s not found, skipping...", fmt.name, track["id"])
            else:
                if "preview" in url.parts:
                    self.log.warning("Format '%s' from track %s is a preview, skipping...", fmt.name, track["id"])
                    continue
                return AudioSource(
                    id=fmt.name,
                    url=url,
                    ext=self.get_filename_and_ext(f"{fmt.name}{fmt.suffix}", mime_type=fmt.mime_type).suffix,
                )

        raise ScrapeError(422, "None of the formats are available")


@HTTPConfig(rate_limit=(3, 5))
class SoundCloudAPI(API):
    ENTRYPOINT: ClassVar[AbsoluteHttpURL] = AbsoluteHttpURL("https://api-v2.soundcloud.com")

    def _resolve(self, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        return (self.ENTRYPOINT / "resolve").with_query(url=str(url))

    async def get(self, url: AbsoluteHttpURL) -> dict[str, Any]:
        for retry in (True, False):
            try:
                return await self.request_json(url.update_query(client_id=await self.client_id()))
            except DownloadError as e:
                if retry and e.status in (401, 403):
                    self.client_id.clear()
                    continue
                raise
        raise RuntimeError

    @disk_cached_method(ttl=86_400 * 10)
    async def client_id(self) -> str:
        async with self.request(self.PRIMARY_URL) as resp:
            soup = await resp.soup(parse_only="script")

        sources = tuple(
            url
            for url in map(self.parse_url, css.iselect(soup, "script[src]", "src"))
            if url.host.endswith(".sndcdn.com") and url.suffix == ".js"
        )
        for script_src in reversed(sources):
            try:
                script = await self.request_text(script_src)
            except Exception:
                self.log.exception("Unable to get client id from %s", script_src)
            else:
                if m := re.search(r'client_id\s*:\s*"([0-9a-zA-Z]{32})"', script):
                    self.log.debug("Found new client_id in %s", script_src)
                    return m[1]

        raise LoginError("Unable to get a valid client id")

    async def stream(self, url: AbsoluteHttpURL) -> AbsoluteHttpURL:
        resp = await self.get(url)
        return self.parse_url(resp["url"])

    async def track(self, track_id: str, secret_token: str | None = None) -> Track:
        url = self.ENTRYPOINT / "tracks" / track_id
        if secret_token:
            url = url.update_query(secret_token=secret_token)
        resp = await self.get(url)
        return _normalize_track(resp, secret_token)

    async def track_by_url(self, url: AbsoluteHttpURL) -> Track:
        resp = await self.get(self._resolve(url))
        return _normalize_track(resp, url.query.get("secret_token"))

    async def original(self, track_id: int, secret_token: str | None) -> AudioSource:
        url = self.ENTRYPOINT / f"tracks/{track_id}/download"
        if secret_token:
            url = url.update_query(secret_token=secret_token)

        msg = f"Unable to get original format for track {track_id}"
        try:
            resp = await self.get(url)
        except DownloadError as e:
            match e.status:
                case 429:
                    raise
                case 401:
                    msg += ". Original download is only available for logged in users"
                case 403:
                    msg += ". Original download not available for this client"
                case _:
                    pass

            self.log.warning(msg)
            raise ScrapeError(e.status or 422, msg) from None

        url = self.parse_url(resp["redirectUri"])
        try:
            async with self.request(url, "HEAD") as resp:
                return AudioSource(
                    id="original",
                    url=resp.url,
                    ext=get_filename_and_ext(resp.filename, mime_type=resp.content_type).suffix,
                )

        except DownloadError as e:
            self.log.warning(msg)
            raise ScrapeError(e.status or 422, msg) from None


class Track(TypedDict):
    id: int
    title: str
    downloadable: NotRequired[bool]
    has_downloads_left: NotRequired[bool]
    user: User
    policy: str
    created_at: str
    permalink_url: str
    tags: tuple[str, ...]
    artwork_url: str
    secret_token: str | None
    formats: tuple[Format, ...]
    artist: str | None


class User(TypedDict, total=False):
    id: Required[int]
    username: Required[str]


@struct
class AudioSource:
    id: str
    url: AbsoluteHttpURL
    ext: str


@struct
class Format:
    protocol: Literal["progressive", "hls", "encrypted-hls"]
    name: str
    abr: int | None
    url: AbsoluteHttpURL
    mime_type: str
    codec: str | None
    suffix: str
    is_preview: bool = False
    is_hq: bool = False

    def score(self) -> tuple[int, ...]:
        return (
            (not self.is_preview),
            self.is_hq,
            bool(self.abr and self.abr >= 160),
            self.protocol == "progressive",
        )


def _normalize_track(track: dict[str, Any], secret_token: str | None = None) -> Track:
    track["tags"] = tuple(re.findall(r'"([^"]+)"|([^ ]+)', track.get("tags_list", "")))
    track["formats"] = tuple(_parse_formats(track))
    track["artist"] = (track.get("publisher_metadata") or {}).get("artist") or None
    track["secret_token"] = secret_token or None
    return cast("Track", cast("object", track))


def _extract_formats(track: dict[str, Any]) -> Generator[tuple[str, bool, dict[str, Any]]]:
    for _, fmt in traversal.find_objs(track.pop("media", None), "url", "preset"):
        format_url = parse_http_url(fmt["url"])
        protocol = fmt["format"]["protocol"]
        has_drm: bool = False

        if protocol.startswith(("ctr-", "cbc-")):
            has_drm = True

        elif "encrypted-hls" in format_url.parts:
            protocol = "encrypted-hls"

        elif "hls" in format_url.parts:
            protocol = "hls"

        yield protocol, has_drm, fmt


def _parse_codecs(mime_type: str) -> str | None:
    try:
        return extr_text(mime_type, r'codecs="', '"')
    except ValueError:
        return None


def _parse_formats(track: dict[str, Any]) -> list[Format]:  # noqa: C901
    formats: list[Format] = []
    drm_formats: list[str] = []
    protocol_map = {"progressive": None, "hls": "hls", "encrypted-hls": "hls-aes"}

    for protocol, has_drm, fmt in _extract_formats(track):
        url = parse_http_url(fmt["url"])
        preset: str = fmt["preset"]
        fmt_name = preset.partition("_")[0]
        fmt_id = f"{protocol}_{fmt_name}"

        if has_drm:
            drm_formats.append(fmt_id)
            continue

        if fmt_name == "abr":
            SoundCloudCrawler.get_logger().warning(
                "Skipping '%s' format for track_id %s: %s", fmt_name, track["id"], fmt_id
            )
            continue

        if protocol not in protocol_map:
            SoundCloudCrawler.get_logger().warning(
                "Skipping unsupported protocol for track %s: %s", track["id"], fmt_id
            )
            continue

        mime_type = fmt["format"]["mime_type"]
        codec = ext = _parse_codecs(mime_type)
        if codec:
            ext = {"mp4a": "m4a", "opus": "opus"}.get(codec[:4])
            mime_type = mime_type.partition(";")[0]

        else:
            ext = mimetypes.guess_extension(mime_type)

        if not ext or ext == "m3u8":
            ext = fmt_name

        is_hq = bool(fmt.get("quality") == "hq")
        abr = int(m[1]) if (m := re.search(r"(\d+)k$", preset)) else 256 if is_hq and "aac" in preset else None
        is_preview = fmt.get("snipped") or "preview" in url.parts

        formats.append(
            Format(
                name="_".join(filter(None, (protocol_map[protocol], preset, "preview" if is_preview else ""))),
                url=url,
                protocol=protocol,  # pyright: ignore[reportArgumentType]
                mime_type=mime_type,
                codec=codec,
                abr=abr,
                is_hq=is_hq,
                is_preview=fmt.get("snipped") or "preview" in url.parts,
                suffix=f".{ext.lstrip('.')}",
            )
        )

    if drm_formats:
        SoundCloudCrawler.get_logger().warning(
            "Skipping DRM protected formats for track %s: %s", track["id"], tuple(drm_formats)
        )

    if not formats:
        if drm_formats:
            raise ScrapeError("DRM", f"{track['id']} only has DRM protected formats: {tuple(drm_formats)}")

        if track.get("policy") == "BLOCK":
            raise ScrapeError(403, "Geo blocked")

    return formats
