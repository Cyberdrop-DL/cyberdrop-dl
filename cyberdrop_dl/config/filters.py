from __future__ import annotations

import dataclasses
import datetime  # noqa: TC003
import re  # noqa: TC003
from typing import TYPE_CHECKING, Self

from cyclopts import Parameter
from pydantic import Field

from cyberdrop_dl.models import ConfigGroup, ConfigModel
from cyberdrop_dl.models.types import ByteSizeSerilized, FalsyAsNone, NonEmptyStr, Timedelta  # noqa: TC001

if TYPE_CHECKING:
    from collections.abc import Callable


def _limit_suffix(suffix: str) -> Callable[[str], str]:
    def transform(name: str) -> str:
        return name if name in {"min", "max"} else f"{name}.{suffix}"

    return transform


@dataclasses.dataclass(slots=True, frozen=True)
class _FloatRange:
    min: float
    max: float

    def __post_init__(self) -> None:
        if not self.max:
            object.__setattr__(self, "max", float("inf"))

    def __contains__(self, value: float, /) -> bool:
        return self.min <= value <= self.max

    @classmethod
    def parse(cls, min: float | None, max: float | None) -> Self | None:  # noqa: A002
        if not min and not max:
            return None
        return cls(min or 0, max or float("inf"))


@dataclasses.dataclass(slots=True, frozen=True)
class _FileSizeRanges:
    video: _FloatRange | None
    image: _FloatRange | None
    audio: _FloatRange | None
    non_media: _FloatRange | None


class _SizeLimit(ConfigModel):
    min: ByteSizeSerilized | None = None
    max: ByteSizeSerilized | None = None


@Parameter(name="*", name_transform=_limit_suffix("size"))
class _FileSizes(ConfigModel):
    image: _SizeLimit = Field(default_factory=_SizeLimit)
    video: _SizeLimit = Field(default_factory=_SizeLimit)
    audio: _SizeLimit = Field(default_factory=_SizeLimit)
    non_media: _SizeLimit = Field(default_factory=_SizeLimit)
    _ranges: _FileSizeRanges | None = None

    @property
    def ranges(self) -> _FileSizeRanges:
        if self._ranges is None:
            self._ranges = _FileSizeRanges(
                video=_FloatRange.parse(
                    self.video.min,
                    self.video.max,
                ),
                image=_FloatRange.parse(
                    self.image.min,
                    self.image.max,
                ),
                non_media=_FloatRange.parse(
                    self.non_media.min,
                    self.non_media.max,
                ),
                audio=_FloatRange.parse(
                    self.audio.min,
                    self.audio.max,
                ),
            )
        return self._ranges


@dataclasses.dataclass(slots=True, frozen=True)
class _DurationRanges:
    video: _FloatRange | None
    audio: _FloatRange | None


class _DurationLimit(ConfigModel):
    min: Timedelta | None = None
    max: Timedelta | None = None


@Parameter(name="*", name_transform=_limit_suffix("duration"))
class _DurationLimits(ConfigModel):
    video: _DurationLimit = Field(default_factory=_DurationLimit)
    audio: _DurationLimit = Field(default_factory=_DurationLimit)
    _ranges: _DurationRanges | None = None

    @property
    def needs_ffmpeg(self) -> bool:
        return bool(self.video.min or self.video.max or self.audio.min or self.audio.max)

    @property
    def ranges(self) -> _DurationRanges:
        if self._ranges is None:
            self._ranges = _DurationRanges(
                video=_FloatRange.parse(
                    self.video.min.total_seconds() if self.video.min else None,
                    self.video.max.total_seconds() if self.video.max else None,
                ),
                audio=_FloatRange.parse(
                    self.audio.min.total_seconds() if self.audio.min else None,
                    self.audio.max.total_seconds() if self.audio.max else None,
                ),
            )
        return self._ranges


@Parameter(name="*")
class _FileFilter(ConfigModel):
    audio: bool = True
    "Download/skip audio files"

    images: bool = True
    "Download/skip image files"

    videos: bool = True
    "Download/skip videos"

    non_media: bool = True
    "Download/skip non media files (.txt, zip, .rar, etc...)"


class Filters(ConfigGroup):
    files: _FileFilter = Field(default_factory=_FileFilter)
    sizes: _FileSizes = Field(default_factory=_FileSizes)
    duration: _DurationLimits = Field(default_factory=_DurationLimits)
    before: FalsyAsNone[datetime.date] = None
    "Only download files uploaded before this date"

    after: FalsyAsNone[datetime.date] = None
    "Only download files uploaded after this date"

    filename_regex: FalsyAsNone[re.Pattern[str]] = None
    "Only download files that match this regex"

    only_hosts: set[NonEmptyStr] = Field(default_factory=set)
    "Only scrape/download from these domains"

    skip_hosts: set[NonEmptyStr] = Field(default_factory=set)
    "Skip scrape/download from these domains"

    allow_files_with_no_extension: bool = False
    "Download potentially dangerous files that have no extension"
