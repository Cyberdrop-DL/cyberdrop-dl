from __future__ import annotations

import dataclasses
import sys
from typing import TYPE_CHECKING, Any, ClassVar, Final, Protocol, Self, dataclass_transform, overload

from cyberdrop_dl.constants import MISSING
from cyberdrop_dl.utils import fast_cache

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterator, Mapping, MutableMapping


class _DataClass(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Any]]


_FIELDS_CACHE: dict[type, tuple[str, ...]] = {}


@fast_cache
def fields_names(cls: type[_DataClass]) -> tuple[str, ...]:
    return tuple(f.name for f in dataclasses.fields(cls) if f.init)


def filter_data[DataClassT: _DataClass](cls: type[DataClassT], data: Mapping[str, Any], /) -> dict[str, Any]:
    return {name: value for name in fields_names(cls) if (value := data.get(name, MISSING)) is not MISSING}


@dataclasses.dataclass(slots=True, frozen=True, eq=False)
class Deserializer:
    aliases: Mapping[str, str] | None = None
    converters: Mapping[str, Callable[[Any], Any]] | None = None

    def __call__[T: _DataClass](self, cls: type[T], data: Mapping[str, Any], **overrides: Any) -> T:
        params = filter_data(cls, data)
        if overrides:
            params.update(overrides)

        for name, value in self._extract_aliases(data):
            params.setdefault(name, value)

        self._apply_converters(params)
        return cls(**params)

    def _extract_aliases(self, data: Mapping[str, Any]) -> Generator[tuple[str, Any]]:
        if self.aliases:
            for name, alias in self.aliases.items():
                try:
                    value = data[alias]
                except KeyError:
                    continue
                yield name, value

    def _apply_converters(self, params: MutableMapping[str, Any]) -> None:
        if self.converters:
            for name, coerce in self.converters.items():
                try:
                    value = params[name]
                except KeyError:
                    continue

                params[name] = coerce(value)


deserialize = Deserializer()


class DictDataclass(_DataClass, Protocol):
    def __iter__(self) -> Iterator[tuple[str, Any]]:
        for field_name in fields_names(type(self)):
            yield field_name, getattr(self, field_name)

    filter_dict = classmethod(filter_data)  # pyright: ignore[reportUnannotatedClassAttribute]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], /, **overrides: Any) -> Self:
        data = cls.filter_dict(data)
        if overrides:
            data.update(overrides)
        return cls(**data)


@overload
def frozen[T](cls: None = None, *, order: bool = False) -> Callable[[type[T]], type[T]]: ...


@overload
def frozen[T](cls: type[T], *, order: bool = False) -> type[T]: ...


@dataclass_transform(frozen_default=True, kw_only_default=True)
def frozen[T](cls: type[T] | None = None, *, order: bool = False) -> Callable[[type[T]], type[T]] | type[T]:
    fn = dataclasses.dataclass(frozen=True, kw_only=True, order=order, slots=True)
    return fn if cls is None else fn(cls)


@frozen
class ConfigDataclass:
    __attr_name__: ClassVar[str]
    __iter__: ClassVar[Final] = DictDataclass.__iter__

    def _changes(self) -> dict[str, Any]:
        return {k: v for k, v in self if v is not None}

    @classmethod
    def get(cls, obj: object) -> Self | None:
        return getattr(obj, cls.__attr_name__, None)

    if sys.version_info < (3, 13, 0):
        __replace__ = dataclasses.replace

    def __or__(self, other: Self) -> Self:
        return self.__replace__(**other._changes())

    def __call__[T](self, obj: type[T]) -> type[T]:
        cfg = current_cfg | self if (current_cfg := self.get(obj)) is not None else self
        setattr(obj, self.__attr_name__, cfg)
        return obj
