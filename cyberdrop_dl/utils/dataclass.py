from __future__ import annotations

import dataclasses
import sys
from typing import TYPE_CHECKING, Any, ClassVar, Final, Literal, Protocol, Self, dataclass_transform, overload

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
def struct[T](
    cls: None = None,
    *,
    order: bool = False,
    kw_only: bool = True,
    frozen: bool = True,
    extras: Literal["forbid", "ignore"] = "forbid",
) -> Callable[[type[T]], type[T]]: ...


@overload
def struct[T](
    cls: type[T],
    *,
    order: bool = False,
    kw_only: bool = True,
    frozen: bool = True,
    extras: Literal["forbid", "ignore"] = "forbid",
) -> type[T]: ...


@dataclass_transform(frozen_default=True, kw_only_default=True)
def struct[T](
    cls: type[T] | None = None,
    *,
    order: bool = False,
    kw_only: bool = True,
    frozen: bool = True,
    extras: Literal["forbid", "ignore"] = "forbid",
) -> Callable[[type[T]], type[T]] | type[T]:

    def wrap(cls: type[T]) -> type[T]:
        dt_cls = dataclasses.dataclass(frozen=frozen, kw_only=kw_only, order=order, slots=True)(cls)
        if extras == "ignore":
            return filter_unknown_kwargs(dt_cls)  # pyright: ignore[reportUnknownVariableType, reportArgumentType]

        return dt_cls

    if cls is None:
        return wrap

    return wrap(cls)


def filter_unknown_kwargs[**P, T: _DataClass](cls: type[T]) -> type[T]:
    """Replace __init__ to filter out invalid kwargs.

    Unknown keys are silently dropped before calling the original __init__.
    """
    original_init = cls.__init__

    def init(self: T, *args: P.args, **kwargs: P.kwargs) -> None:
        original_init(self, *args, **filter_data(type(self), kwargs))

    cls.__init__ = init
    return cls


CONFIG_REGISTRY: dict[str, type[ConfigDataclass]] = {}


@struct
class ConfigDataclass:
    __attr_name__: ClassVar[str]
    __iter__: ClassVar[Final] = DictDataclass.__iter__

    def __init_subclass__(cls) -> None:
        if not fields_names(cls):  # Not a dataclass yet, wait until the @dataclass decorator recreates the class
            return
        assert cls.__attr_name__
        assert cls.__attr_name__.startswith("__"), f"{cls.__attr_name__ = } must be a dunder name"
        assert cls.__attr_name__ not in CONFIG_REGISTRY, (
            f"A config with {cls.__attr_name__ = } already exists: {CONFIG_REGISTRY[cls.__attr_name__]!r}"
        )
        CONFIG_REGISTRY[cls.__attr_name__] = cls

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
