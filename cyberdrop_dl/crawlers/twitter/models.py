# Simplified version of https://github.com/FxEmbed/FxEmbed/blob/07612ab44d1a489489e97f0b219d09dcfdb10081/docs/specs/fxtwitter-openapi.json
from __future__ import annotations

import dataclasses
import itertools
import operator
from typing import TYPE_CHECKING, Any, ClassVar, Literal, final

from typing_extensions import TypedDict

from cyberdrop_dl.models import DeferredModel

if TYPE_CHECKING:
    from collections.abc import Generator


class Author(TypedDict):
    type: Literal["profile"]
    id: str
    name: str
    screen_name: str


@dataclasses.dataclass(slots=True)
class Photo:
    id: str
    type: Literal["photo", "gif"]
    url: str
    height: int
    width: int
    format: str | None = None
    altText: str | None = None  # noqa: N815
    transcode_url: str | None = None


@final
@dataclasses.dataclass(slots=True)
class VideoFormat:
    SORT_KEY: ClassVar = operator.attrgetter("score")

    url: str
    container: Literal["mp4", "webm", "m3u8"] | None = None
    codec: Literal["h264", "hevc", "vp9", "av1"] | None = None
    bitrate: float | None = None

    @property
    def score(self) -> tuple[int, int, float]:
        return (
            self.container != "m3u8",
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
    formats: list[VideoFormat] = dataclasses.field(default_factory=list)

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
class PostMedia:
    external: ExternalMedia | None = None
    photos: list[Photo] = dataclasses.field(default_factory=list)
    videos: list[Video] = dataclasses.field(default_factory=list)
    mosaic: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    broadcast: list[dict[str, Any]] = dataclasses.field(default_factory=list)

    def __iter__(self) -> Generator[tuple[Photo | Video | ExternalMedia, bool]]:
        for media in itertools.chain(self.photos, self.videos):
            yield media, False

        if self.external:
            yield self.external, True


@dataclasses.dataclass(slots=True)
class CardImage:
    width: float | None = None
    height: float | None = None
    url: str | None = None
    alt: str | None = None


@dataclasses.dataclass(slots=True)
class Card:
    """Preview card for external links. (AKA embed)"""

    url: str
    title: str | None = None
    description: str | None = None
    domain: str | None = None
    card_name: str | None = None
    image: CardImage | None = None


class Tweet(DeferredModel):
    type: Literal["status"]
    id: str
    url: str
    text: str
    created_at: str
    created_timestamp: int
    likes: int
    reposts: int
    quotes: int
    replies: int
    author: Author
    media: PostMedia
    card: Card | None = None
    lang: str | None = None
