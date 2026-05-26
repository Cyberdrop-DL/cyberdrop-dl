from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, Self, TypeVar

from pydantic import TypeAdapter
from typing_extensions import Sentinel

if TYPE_CHECKING:
    from collections.abc import Mapping


class _DataClass(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Any]]


_DataClassT = TypeVar("_DataClassT", bound=_DataClass)


_FIELDS_CACHE: dict[type, tuple[str, ...]] = {}
_TYPE_ADAPTER_CACHE: dict[type[_DataClass], TypeAdapter[_DataClass]] = {}
_MISSING = Sentinel("_MISSING")


def _fields(cls: type[_DataClass]) -> tuple[str, ...]:
    if fields := _FIELDS_CACHE.get(cls):
        return fields
    fields = _FIELDS_CACHE[cls] = tuple(f.name for f in dataclasses.fields(cls) if f.init)
    return fields


def filter_data(cls: type[_DataClassT], data: Mapping[str, Any], /) -> dict[str, Any]:
    return {name: value for name in _fields(cls) if (value := data.get(name, _MISSING)) is not _MISSING}


def deserialize(cls: type[_DataClassT], data: Mapping[str, Any], /, **overrides: Any) -> _DataClassT:
    """Parses 'data' to build an instance of 'cls' without type validation"""
    data = filter_data(cls, data)
    if overrides:
        data.update(overrides)
    return cls(**data)


def type_adapter(cls: type[_DataClassT]) -> TypeAdapter[type[_DataClassT]]:
    """Get a type adapter for this class.

    Type adapters are cached. Multiple calls return the same adapter"""
    if adapter := _TYPE_ADAPTER_CACHE.get(cls):
        return adapter  # pyright: ignore[reportReturnType]
    adapter = _TYPE_ADAPTER_CACHE[cls] = TypeAdapter(cls)
    return adapter  # pyright: ignore[reportReturnType]


class DictDataclass(_DataClass, Protocol):
    filter_dict = classmethod(filter_data)  # pyright: ignore[reportUnannotatedClassAttribute]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], /, **overrides: Any) -> Self:
        data = cls.filter_dict(data)
        if overrides:
            data.update(overrides)
        return cls(**data)
