from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, Self, TypeVar

from typing_extensions import Sentinel

if TYPE_CHECKING:
    from collections.abc import Mapping


class _DataClass(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Any]]


_DataClassT = TypeVar("_DataClassT", bound=_DataClass)


_FIELDS_CACHE: dict[type, tuple[str, ...]] = {}
_MISSING = Sentinel("_MISSING")


def _fields(cls: type[_DataClass]) -> tuple[str, ...]:
    if fields := _FIELDS_CACHE.get(cls):
        return fields
    fields = _FIELDS_CACHE[cls] = tuple(f.name for f in dataclasses.fields(cls) if f.init)
    return fields


def filter_data(cls: type[_DataClassT], data: Mapping[str, Any], /) -> dict[str, Any]:
    return {name: value for name in _fields(cls) if (value := data.get(name, _MISSING)) is not _MISSING}


def deserealize(cls: type[_DataClassT], data: dict[str, Any], /, **overrides: Any) -> _DataClassT:
    if overrides:
        data.update(overrides)
    return cls(**filter_data(cls, data))


class DictDataclass(_DataClass, Protocol):
    filter_dict = classmethod(filter_data)  # pyright: ignore[reportUnannotatedClassAttribute]

    @classmethod
    def from_dict(cls, data: dict[str, Any], /, **overrides: Any) -> Self:
        if overrides:
            data.update(overrides)
        return cls(**cls.filter_dict(data))
