from __future__ import annotations

import datetime
import operator
from typing import Annotated, Any, ClassVar, Literal, final

from pydantic import Field, PlainValidator, dataclasses


@dataclasses.dataclass(slots=True)
class Verification:
    verified: bool
    type: Literal["organization", "government", "individual"] | None
    verified_at: str | None = None
    identity_verified: bool | None = None
    verified_by: str | None = None


@dataclasses.dataclass(slots=True)
class Author:
    type: Literal["profile"]
    id: str
    name: str
    screen_name: str
    avatar_url: str
    banner_url: str
    description: str
    location: str
    url: str
    protected: bool
    followers: int
    following: int
    media_count: int
    likes: int
    joined: str
    birthday: Annotated[datetime.date | None, PlainValidator(lambda x: x and datetime.date(**x))]
    verification: Verification


@dataclasses.dataclass(slots=True)
class Photo:
    id: str
    format: str
    type: Literal["photo", "gif"]
    url: str
    height: int
    width: int
    altText: str  # noqa: N815
    transcode_url: str | None = None


@final
@dataclasses.dataclass(slots=True)
class VideoFormat:
    url: str
    container: Literal["mp4", "webm", "m3u8"] | None = None
    codec: Literal["h264", "hevc", "vp9", "av1"] | None = None
    bitrate: float | None = None

    SORT_KEY: ClassVar = operator.attrgetter("score")

    @property
    def score(self) -> tuple[int, int, float]:
        return (
            (None, "mp4", "webm", "m3u8").index(self.container),
            (None, "vp9", "h264", "hevc", "av1").index(self.codec),
            self.bitrate or 0,
        )


@dataclasses.dataclass(slots=True)
class Video:
    type: Literal["video", "gif"]
    url: str
    width: float
    height: float
    duration: float
    id: str | None = None
    format: str | None = None
    thumbnail_url: str | None = None
    transcode_url: str | None = None
    filesize: float | None = None
    formats: list[VideoFormat] = Field(default_factory=list)

    @property
    def best_format(self) -> VideoFormat:
        return max(self.formats, key=VideoFormat.SORT_KEY)


@dataclasses.dataclass(slots=True)
class ExternalMedia:
    type: str
    url: str
    thumbnail_url: str | None = None
    height: int | None = None
    width: int | None = None


@dataclasses.dataclass(slots=True)
class Media:
    external: ExternalMedia | None = None
    photos: list[Photo] = Field(default_factory=list)
    videos: list[Video] = Field(default_factory=list)
    mosaic: list[dict[str, Any]] = Field(default_factory=list)
    broadcast: list[dict[str, Any]] = Field(default_factory=list)


@dataclasses.dataclass(slots=True)
class Status:
    type: str
    id: str
    url: str
    text: str
    created_at: str
    created_timestamp: int
    provider: Literal["twitter"]
    likes: int
    reposts: int
    quotes: int
    replies: int
    lang: str
    possibly_sensitive: bool
    author: Author
    media: Media
