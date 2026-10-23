from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, override

from cyberdrop_dl.crawlers.vk import unblur
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import parse_url
from cyberdrop_dl.utils.dataclass import deserialize

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from cyberdrop_dl.url_objects import AbsoluteHttpURL


class APIObject:
    parse = classmethod(deserialize)


@dataclasses.dataclass(slots=True, frozen=True)
class Post(APIObject):
    date: int
    id: int
    from_id: int
    owner_id: int
    attachments: list[dict[str, Any]]
    text: str | None = None


@dataclasses.dataclass(slots=True, frozen=True)
class Owner(APIObject):
    id: int
    type: str
    screen_name: str | None = None
    name: str | None = None
    first_name: str | None = None
    last_name: str | None = None

    @property
    def full_name(self) -> str:
        return (
            " ".join(filter(None, (self.first_name, self.last_name))) or self.name or self.screen_name or str(self.id)
        )


@dataclasses.dataclass(slots=True, frozen=True)
class Format(APIObject):
    name: str
    url: AbsoluteHttpURL
    height: int | None = None
    hls: bool = False

    @property
    def score(self) -> tuple[bool, int]:
        return (not self.hls, self.height or 0)


@dataclasses.dataclass(slots=True, frozen=True)
class Video(APIObject):
    id: int
    owner_id: int
    title: str
    thumb: str | None
    date: int
    embed: str | None
    formats: tuple[Format, ...]
    type: str = "video"
    access_key: str | None = None

    @override
    @classmethod
    def parse(cls, video: dict[str, Any]) -> Video:
        return deserialize(
            cls,
            video,
            thumb=thumbs[-1]["url"] if (thumbs := video.get("image")) else None,
            formats=tuple(_extract_formats(video)),
            embed=video.get("files", {}).get("external"),
        )

    @property
    def slug(self) -> str:
        return f"{self.owner_id}_{self.id}"

    @property
    def prefix(self) -> str:
        return "clip" if self.type == "short_video" else "video"

    @property
    def web_path(self) -> str:
        return f"{self.prefix}{self.slug}"


@dataclasses.dataclass(slots=True, frozen=True)
class PhotoSize(APIObject):
    TYPES: ClassVar[tuple[str, ...]] = (
        "base",
        "s",
        "m",
        "o",
        "p",
        "q",
        "r",
        "x",
        "y",
        "z",
        "w",
        "orig",
    )  # worst to best
    type: str
    url: AbsoluteHttpURL
    height: int | None = None
    width: int | None = None

    def score(self) -> int:
        try:
            return self.TYPES.index(self.type)
        except ValueError:
            raise ScrapeError(422, f"Unknown size for {self}") from None


@dataclasses.dataclass(slots=True, frozen=True)
class Photo(APIObject):
    id: int
    owner_id: int
    date: int
    sources: tuple[PhotoSize, ...]

    @property
    def slug(self) -> str:
        return f"{self.owner_id}_{self.id}"

    @property
    def web_path(self) -> str:
        return f"photo{self.slug}"

    @override
    @classmethod
    def parse(cls, photo: dict[str, Any]) -> Photo:
        origin = parse_url(base) if (base := photo.get("base")) else None

        def parse_src(size: dict[str, Any], name: str | None = None) -> PhotoSize:
            url = parse_url(size["url"], origin)
            return PhotoSize.parse(size, type=name or size["type"], url=unblur(url))

        def sources() -> Iterable[PhotoSize]:
            if orig := photo.get("orig_photo"):
                yield parse_src(orig, "orig")

            yield from map(parse_src, photo["sizes"])

        return deserialize(cls, photo, sources=tuple(sources()))


@dataclasses.dataclass(slots=True, frozen=True)
class Audio(APIObject):
    id: int
    owner_id: int
    artist: str
    title: str
    url: str
    date: int
    album_id: int | None = None


@dataclasses.dataclass(slots=True, frozen=True)
class Graffiti(APIObject):
    id: int
    owner_id: int
    photo_130: str
    photo_604: str


@dataclasses.dataclass(slots=True, frozen=True)
class File(APIObject):
    id: int
    owner_id: int
    title: str
    ext: str
    url: str
    date: int


@dataclasses.dataclass(slots=True, frozen=True)
class Link(APIObject):
    url: str
    title: str
    description: str
    caption: str | None = None


@dataclasses.dataclass(slots=True, frozen=True)
class Album(APIObject):
    id: int
    owner_id: int
    title: str
    created: int
    size: int


@dataclasses.dataclass(slots=True, frozen=True)
class CatalogSection(APIObject):
    id: str
    next_from: str | None
    videos: list[dict[str, Any]]


def _extract_formats(data: dict[str, Any]) -> Generator[Format]:
    for name, value in data.get("files", {}).items():
        if not value or type(value) is not str or not value.startswith(("//", "http")):
            continue

        url = parse_url(value)

        match name.partition("_"):
            case ["mp4", _, res]:
                yield Format(name=name, url=url, height=int(res))
            case ["hls", *_]:
                yield Format(name=name, url=url, hls=True)
            case _:
                continue
