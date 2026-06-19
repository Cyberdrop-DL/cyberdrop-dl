from __future__ import annotations

import dataclasses
import datetime
import re  # noqa: TC003
from typing import TYPE_CHECKING, Self

from cyclopts import Parameter
from pydantic import ByteSize, Field

from cyberdrop_dl.models import ConfigGroup, DeferedModel
from cyberdrop_dl.models.types import (  # noqa: TC001
    ByteSizeSerilized,
    FalsyAsNone,
    FalsyAsTuple,
    NonEmptyStr,
    RemoveDuplicates,
    Timedelta,
)

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
    def parse(cls, min: float, max: float | None) -> Self | None:  # noqa: A002
        if not min and not max:
            return None
        return cls(min, max or float("inf"))


@dataclasses.dataclass(slots=True, frozen=True)
class _FileSizeRanges:
    video: _FloatRange
    image: _FloatRange
    audio: _FloatRange
    non_media: _FloatRange


class _SizeLimit(DeferedModel):
    min: ByteSizeSerilized = ByteSize(0)
    max: ByteSizeSerilized = ByteSize(0)


@Parameter(name="*", name_transform=_limit_suffix("size"))
class _FileSizes(DeferedModel):
    image: _SizeLimit = Field(default_factory=_SizeLimit)
    video: _SizeLimit = Field(default_factory=_SizeLimit)
    audio: _SizeLimit = Field(default_factory=_SizeLimit)
    non_media: _SizeLimit = Field(default_factory=_SizeLimit)
    _ranges: _FileSizeRanges | None = None

    @property
    def ranges(self) -> _FileSizeRanges:
        if self._ranges is None:
            self._ranges = _FileSizeRanges(
                video=_FloatRange(
                    self.video.min,
                    self.video.max,
                ),
                image=_FloatRange(
                    self.image.min,
                    self.image.max,
                ),
                non_media=_FloatRange(
                    self.non_media.min,
                    self.non_media.max,
                ),
                audio=_FloatRange(
                    self.audio.min,
                    self.audio.max,
                ),
            )
        return self._ranges


@dataclasses.dataclass(slots=True, frozen=True)
class _DurationRanges:
    video: _FloatRange | None
    audio: _FloatRange | None


class _DurationLimit(DeferedModel):
    min: Timedelta = datetime.timedelta(seconds=0)
    max: Timedelta = datetime.timedelta(seconds=0)


@Parameter(name="*", name_transform=_limit_suffix("duration"))
class _DurationLimits(DeferedModel):
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
                    self.video.min.total_seconds(),
                    self.video.max.total_seconds(),
                ),
                audio=_FloatRange.parse(
                    self.audio.min.total_seconds(),
                    self.audio.max.total_seconds(),
                ),
            )
        return self._ranges


@Parameter(name="*")
class _FileFilter(DeferedModel):
    audio: bool = True
    images: bool = True
    videos: bool = True
    non_media: bool = True


class Filters(ConfigGroup):
    files: _FileFilter = Field(default_factory=_FileFilter)
    sizes: _FileSizes = Field(default_factory=_FileSizes)
    duration: _DurationLimits = Field(default_factory=_DurationLimits)
    before: FalsyAsNone[datetime.date] = None
    after: FalsyAsNone[datetime.date] = None
    filename_regex: FalsyAsNone[re.Pattern[str]] = None
    only_hosts: RemoveDuplicates[FalsyAsTuple[NonEmptyStr]] = ()
    skip_hosts: RemoveDuplicates[FalsyAsTuple[NonEmptyStr]] = ()
    allow_files_with_no_extension: bool = False
