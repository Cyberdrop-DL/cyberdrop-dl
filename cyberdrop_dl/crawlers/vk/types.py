from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, Self, override

from cyberdrop_dl.crawlers.vk import full_res_img, try_parse_url
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.utils import parse_url
from cyberdrop_dl.utils.dataclass import deserialize

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from cyberdrop_dl.url_objects import AbsoluteHttpURL


class APIObject:
    parse = classmethod(deserialize)


@dataclasses.dataclass(slots=True, frozen=True)
class Owned(APIObject):
    id: int
    owner_id: int

    @property
    def slug(self) -> str:
        return f"{self.owner_id}_{self.id}"


@dataclasses.dataclass(slots=True, frozen=True)
class Post(Owned):
    date: int
    from_id: int
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
class Video(Owned):
    thumb: str | None
    date: int
    embed: str | None
    formats: tuple[Format, ...]
    type: str = "video"
    title: str | None = None
    access_key: str | None = None
    description: str | None = None

    @override
    @classmethod
    def parse(cls, video: dict[str, Any]) -> Video:
        thumb = (
            max((PhotoSize.parse(p, type="thumb") for p in thumbs), key=PhotoSize.res).url
            if (thumbs := video.get("image"))
            else None
        )

        return deserialize(
            cls,
            video,
            thumb=thumb,
            formats=tuple(_extract_formats(video)),
            embed=video.get("files", {}).get("external"),
        )

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

    def res(self) -> tuple[int, int]:
        return (self.height or 0, self.width or 0)


@dataclasses.dataclass(slots=True, frozen=True)
class Photo(Owned):
    date: int
    sources: tuple[PhotoSize, ...]

    @property
    def web_path(self) -> str:
        return f"photo{self.slug}"

    @override
    @classmethod
    def parse(cls, photo: dict[str, Any]) -> Photo:
        origin = parse_url(base) if (base := photo.get("base")) else None

        def parse_src(size: dict[str, Any], name: str | None = None) -> PhotoSize:
            url = parse_url(size["url"], origin)
            return PhotoSize.parse(size, type=name or size["type"], url=full_res_img(url))

        def sources() -> Iterable[PhotoSize]:
            if orig := photo.get("orig_photo"):
                yield parse_src(orig, "orig")

            yield from map(parse_src, photo["sizes"])

        return deserialize(cls, photo, sources=tuple(sources()))


@dataclasses.dataclass(slots=True, frozen=True)
class Audio(Owned):
    title: str
    date: int
    artist: str | None = None
    album_id: int | None = None
    access_key: str | None = None
    url: str | None = None

    @property
    def web_path(self) -> str:
        return f"audio{self.slug}"


@dataclasses.dataclass(slots=True, frozen=True)
class AudioPlaylist(Owned):
    title: str
    count: int
    type: str
    thumb: Graffiti | None = None
    access_key: str | None = None
    description: str | None = None

    @property
    def web_path(self) -> str:
        return f"audio_playlist{self.slug}"

    @override
    @classmethod
    def parse(cls, playlist: dict[str, Any]) -> Self:
        return deserialize(cls, playlist, thumb=Graffiti.parse(g) if (g := playlist.get("photo")) else None)


@dataclasses.dataclass(slots=True, frozen=True)
class Graffiti(APIObject):  # Old photo format
    sizes: dict[int, AbsoluteHttpURL]

    @override
    @classmethod
    def parse(cls, photo: dict[str, Any]) -> Self:
        def sizes():
            for name, value in photo.items():
                match name.partition("_"):
                    case ["photo", _, size] if size and (url := try_parse_url(value)):
                        yield int(size), full_res_img(url)
                    case _:
                        pass

        return deserialize(cls, photo, sizes=dict(sizes()))

    def best(self) -> AbsoluteHttpURL:
        _, url = max(self.sizes.items())
        return url


@dataclasses.dataclass(slots=True, frozen=True)
class File(Owned):
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
class Album(Owned):
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
        if url := try_parse_url(value):
            match name.partition("_"):
                case ["mp4", _, res]:
                    yield Format(name=name, url=url, height=int(res))
                case ["hls", *_]:
                    yield Format(name=name, url=url, hls=True)
                case _:
                    continue
