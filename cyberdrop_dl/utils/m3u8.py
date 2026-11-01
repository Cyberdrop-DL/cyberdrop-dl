from __future__ import annotations

import dataclasses
import datetime as dt
import logging
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar, Literal, NamedTuple, Self, final

import m3u8.model
from m3u8 import M3U8 as _M3U8
from m3u8 import Media, Playlist
from m3u8.mixins import BasePathMixin, GroupedBasePathMixin

from cyberdrop_dl.exceptions import DownloadError, ScrapeError
from cyberdrop_dl.mediaprops import Codecs, Resolution
from cyberdrop_dl.signature import dataclass_repr, vars_repr
from cyberdrop_dl.utils.dataclass import DictDataclass
from cyberdrop_dl.utils.urls import parse_http_url

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Iterator, Mapping
    from pathlib import Path

    from cyberdrop_dl.url_objects import AbsoluteHttpURL

logger = logging.getLogger(__name__)


BasePathMixin.__repr__ = GroupedBasePathMixin.__repr__ = vars_repr


class MediaType(StrEnum):
    audio = "AUDIO"
    video = "VIDEO"
    subtitles = "SUBTITLES"
    closed_captions = "CLOSED-CAPTIONS"


class MediaList(list[Media]):
    def filter_by(
        self,
        type: MediaType | str | None = None,  # noqa: A002
        group_id: str | None = None,
        language: str | None = None,
        name: str | None = None,
    ) -> Generator[Media]:
        assert any(value is not None for value in (type, group_id, language, name))
        attrs = {name: value for name, value in locals().items() if value is not None and name != "self"}
        for media in self:
            if all(getattr(media, name) == value for name, value in attrs.items()):
                yield media

    def filter(
        self,
        type: MediaType | str | None = None,  # noqa: A002
        group_id: str | None = None,
        language: str | None = None,
        name: str | None = None,
    ) -> MediaList:
        return MediaList(self.filter_by(type, group_id, language, name))

    def get_default(self) -> Media | None:
        if self:
            autoselect = None
            for media in self:
                if media.default == "YES":
                    return media
                if media.autoselect == "YES" and autoselect is None:
                    autoselect = media
            return autoselect


class MediaURLs(NamedTuple):
    video: AbsoluteHttpURL
    audio: AbsoluteHttpURL | None
    subtitle: AbsoluteHttpURL | None

    def with_query(self, query: Mapping[str, Any]) -> MediaURLs:
        return MediaURLs(
            video=self.video.with_query(query),
            audio=self.audio and self.audio.with_query(query),
            subtitle=self.subtitle and self.subtitle.with_query(query),
        )


@dataclasses.dataclass(slots=True)
class Rendition:
    video: M3U8
    audio: M3U8 | None
    subtitle: M3U8 | None

    def __iter__(self) -> Iterator[M3U8 | None]:
        yield from (self.video, self.audio, self.subtitle)


@final
@dataclasses.dataclass(frozen=True, slots=True, order=True)
class StreamInfo:
    """Exactly the same as m3u8.model.StreamInfo but as a dataclass, to support sorting rendition groups with the same resolution but different bitrates (bandwidth)"""

    bandwidth: int | None
    closed_captions: Any | None
    average_bandwidth: int | None
    program_id: int | None
    resolution: tuple[int, int] | None
    codecs: str | None
    audio: str | None
    video: str | None
    subtitles: str | None
    frame_rate: float | None
    video_range: str | None
    hdcp_level: str | None
    pathway_id: str | None
    stable_variant_id: str | None
    req_video_layout: str | None

    __str__ = m3u8.model.StreamInfo.__str__
    __iter__ = DictDataclass.__iter__


@dataclasses.dataclass(frozen=True, slots=True, order=True)
class RenditionDetails:
    resolution: Resolution
    stream_info: StreamInfo
    codecs: Codecs
    media: MediaList
    urls: MediaURLs

    def __json__(self) -> dict[str, Any]:
        return {"stream": dict(self.stream_info), "urls": self.urls._asdict()}

    @staticmethod
    def new(playlist: Playlist) -> RenditionDetails:
        assert playlist.uri

        def get_url(m3u8_obj: Playlist | Media) -> AbsoluteHttpURL:
            return parse_http_url(m3u8_obj.absolute_uri, trim=False)

        video_url = get_url(playlist)
        subtitle_url = audio_url = None

        stream_info = StreamInfo(**vars(playlist.stream_info))
        resolution = _parse_stream_resolution(stream_info, video_url)
        codecs = Codecs.parse(playlist.stream_info.codecs or "")
        media = MediaList(playlist.media)

        if audio_group_id := playlist.stream_info.audio:
            audio = next(media.filter_by(type=MediaType.audio, group_id=audio_group_id))
            audio_url: AbsoluteHttpURL | None = get_url(audio)

        if subtitle_group_id := playlist.stream_info.subtitles:
            subtitle = next(media.filter_by(type=MediaType.subtitles, group_id=subtitle_group_id))
            subtitle_url: AbsoluteHttpURL | None = get_url(subtitle)

        media_urls = MediaURLs(video_url, audio_url, subtitle_url)

        return RenditionDetails(resolution, stream_info, codecs, media, media_urls)


def _parse_stream_resolution(stream_info: StreamInfo, video_url: AbsoluteHttpURL) -> Resolution:
    if stream_info.resolution is not None:
        return Resolution(*stream_info.resolution)
    try:
        return get_resolution_from_url(video_url)
    except RuntimeError:
        if stream_info.bandwidth is None:
            raise ValueError("Stream has no resolution or bandwidth information") from None
        return Resolution.unknown()


class Encryption(StrEnum):
    AES_128 = "AES-128"


@dataclasses.dataclass(slots=True, frozen=True)
class HLSKey:
    __attr__: ClassVar[str] = "HLS_DECRYPT_INFO"
    method: Encryption
    uri: AbsoluteHttpURL
    iv: bytes

    @classmethod
    def get(cls, data: Mapping[str, Any]) -> Self | None:
        key = data.get(cls.__attr__)
        if type(key) is cls:
            return key

    def __call__(self, data: dict[str, Any]) -> Self | None:
        key = data.setdefault(self.__attr__, self)
        if key is not self:
            raise RuntimeError("Another key is already set")

    @classmethod
    def parse(cls, seg: m3u8.model.Segment | m3u8.model.InitializationSection, idx: int) -> Self | None:
        if isinstance(seg, m3u8.model.Segment) and seg.key and seg.key.method and seg.key.method != "NONE":
            assert seg.key.uri
            if seg.key.iv:
                iv = bytes.fromhex(seg.key.iv.removeprefix("0x"))
            else:
                media_sequence = seg.media_sequence if seg.media_sequence is not None else idx
                iv = media_sequence.to_bytes(16, "big")

            return cls(
                method=Encryption(seg.key.method),
                iv=iv,
                uri=parse_http_url(seg.key.absolute_uri, trim=False),
            )


def _validate_keys(stream: M3U8) -> None:
    if not stream.keys:
        return
    for key in stream.keys:
        if key is None or key.method == "NONE":  # First one could be None # pyright: ignore[reportUnnecessaryComparison]
            continue
        if key.method != Encryption.AES_128:
            raise DownloadError(
                "Encrypted", f"M3U8 playlist {stream.source} has an unsupported encryption algorithm: \n{key!s}"
            )
        if not key.uri:
            raise DownloadError(
                "Encrypted",
                f"M3U8 playlist {stream.source} is encrypted but we have no URI to fetch to decrypted it: \n{key!s}",
            )


def is_live_stream(m3u8: _M3U8) -> bool:
    return not (m3u8.is_variant or m3u8.is_endlist)


@dataclass_repr("media_type", "base_uri", "is_variant", "source")
class M3U8(_M3U8):
    def __init__(
        self,
        content: str,
        base_uri: AbsoluteHttpURL | None = None,
        media_type: Literal["video", "audio", "subtitle"] | None = None,
        source: AbsoluteHttpURL | Path | None = None,
    ) -> None:
        if base_uri and base_uri.suffix.casefold() == ".m3u8":
            base_uri = base_uri.parent
        self.media_type: Literal["video", "audio", "subtitle"] | None = media_type
        self.source: AbsoluteHttpURL | Path | None = source
        super().__init__(content, base_uri=str(base_uri) if base_uri else None)
        _validate_keys(self)
        if is_live_stream(self):
            raise ScrapeError.live_stream(source)

    @property
    def total_segments(self) -> int:
        return len(self.segment_map) + len(self.segments)

    @property
    def total_duration(self) -> dt.timedelta:
        total_duration: float = sum(duration for segment in self.segments if (duration := segment.duration))
        return dt.timedelta(seconds=total_duration)


class _LazyRenditionLog:
    def __init__(self, groups: list[RenditionDetails]) -> None:
        self.groups: list[RenditionDetails] = groups

    def __json__(self) -> tuple[dict[str, Any], ...]:
        return tuple(rendition.__json__() for rendition in self.groups)

    def __str__(self) -> str:
        return str(self.__json__())


@dataclasses.dataclass(slots=True)
class VariantM3U8Parser:
    """Parses groups inside a variant M3U8"""

    _m3u8: M3U8
    groups: list[RenditionDetails] = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        assert self._m3u8.is_variant
        self.groups = sorted((RenditionDetails.new(playlist) for playlist in self._m3u8.playlists), reverse=True)

    def get_rendition_groups(
        self, only: Iterable[str] = (), *, exclude: Iterable[str] = ()
    ) -> Generator[RenditionDetails]:
        """Yields M3U8 options, best to worst"""
        assert not (only and exclude), "only one of `only` or `exclude` can be supplied, not both"
        if isinstance(exclude, str):
            exclude = (exclude,)
        if isinstance(only, str):
            only = (only,)

        only = tuple(map(Codecs.pretty_name, only))
        exclude = tuple(map(Codecs.pretty_name, exclude))
        for group in self.groups:
            if codec := Codecs.pretty_name(group.codecs.video or ""):
                if only and codec not in only:
                    continue
                if codec in exclude:
                    continue
            yield group

    def get_best_group(self, only: Iterable[str] = (), *, exclude: Iterable[str] = ()) -> RenditionDetails:
        logger.debug("Available renditions from %s:\n%s", self._m3u8.base_uri, _LazyRenditionLog(self.groups))
        return next(self.get_rendition_groups(only=only, exclude=exclude))


def select_best_rendition(
    m3u8_playlist: M3U8, only: Iterable[str] = (), *, exclude: Iterable[str] = ()
) -> RenditionDetails:
    return VariantM3U8Parser(m3u8_playlist).get_best_group(only=only, exclude=exclude)


def get_resolution_from_url(url: AbsoluteHttpURL | str) -> Resolution:
    if isinstance(url, str):
        url = parse_http_url(url, trim=False)  # Raises Invalid URL error for relative URLs

    try:
        return Resolution.parse(url)
    except ValueError:
        raise RuntimeError(f"Unable to parse resolution from {url}") from None
