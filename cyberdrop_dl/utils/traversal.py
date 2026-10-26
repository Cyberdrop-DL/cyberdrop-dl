from __future__ import annotations

import contextlib
from collections.abc import Callable, Generator, Iterable, Iterator, Mapping, Sequence
from typing import Any, TypeGuard, overload

from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.signature import dataclass_repr

type Path = tuple[str | int, ...]
type Validator = Callable[[object], bool]
type Visitor = Callable[[Path, Any], Any]


@dataclass_repr("_traverse_gen", "_results", "_name")
class TraverseResults[T, U]:
    def __init__(self, traverse_gen: Iterable[tuple[T, U]], *, name: str | None = None) -> None:
        self._traverse_gen: Iterable[tuple[T, U]] = traverse_gen
        self._results: int = 0
        self._name: str | None = name

    def __iter__(self) -> Iterator[tuple[T, U]]:
        for pair in self._traverse_gen:
            self._results += 1
            yield pair

    def paths(self) -> Iterator[T]:
        for path, _ in self:
            yield path

    def values(self) -> Iterator[U]:
        for _, value in self:
            yield value

    def first(self, name: str | None = None) -> U:
        if self._results > 0:
            raise RuntimeError("We already yielded the first result")
        name = name or self._name or "a required traverse attribute"
        try:
            return next(self.values())
        except StopIteration as e:
            raise ScrapeError(422, f"Unable to find {name}") from e


@overload
def traverse[T](
    value: object, visitor: Callable[[Path, Any], TypeGuard[T]], path: Path = ()
) -> Generator[tuple[Path, T]]: ...


@overload
def traverse(value: object, visitor: Callable[[Path, Any], bool], path: Path = ()) -> Generator[tuple[Path, Any]]: ...


def traverse(value: object, visitor: Callable[[Path, Any], Any], path: Path = ()) -> Generator[tuple[Path, Any]]:
    if visitor(path, value):
        yield path, value
        return

    match value:
        case dict():
            for key, item in value.items():
                yield from traverse(item, visitor, (*path, key))

        case list() | tuple():
            for index, item in enumerate(value):
                yield from traverse(item, visitor, (*path, index))

        case _:
            pass


def _traverse_many(
    value: object, visitor: Visitor, next_visitors: Sequence[Visitor], *, path: Path = ()
) -> Generator[tuple[Path, Any]]:
    is_last_visitor = len(next_visitors) == 0
    for current_path, inner_value in traverse(value, visitor, path):
        if is_last_visitor:
            yield current_path, inner_value
        else:
            yield from _traverse_many(inner_value, next_visitors[0], next_visitors[1:], path=current_path)


@contextlib.contextmanager
def catch[T](name: str | None = None) -> Generator[None]:
    try:
        yield
    except StopIteration:
        raise ScrapeError(422, f"Unable to find {name}" if name else None) from None


def is_class_info(obj: object) -> TypeGuard[type | tuple[type, ...]]:
    return isinstance(obj, type) or (isinstance(obj, tuple) and all(isinstance(val, type) for val in obj))


def value_visitor[T, R](fn: Callable[[T], R]) -> Callable[[Any, T], R]:

    def visit(_: Any, value: T) -> R:
        return fn(value)

    return visit


def cast_validator(obj: object) -> Validator:
    if obj is ...:
        return lambda _: True
    if is_class_info(obj):
        return lambda x: isinstance(x, obj)

    if callable(obj):
        return lambda x: bool(obj(x))

    return lambda x: x == obj


@dataclass_repr("target_keys", "validators")
class DictVisitor:
    def __init__(self, keys: tuple[str, ...], validate: Mapping[str, Any] | None = None) -> None:
        validate = validate or {}
        self.target_keys: set[str] = set(validate).union(keys)
        self.validators: dict[str, Validator] = {key: cast_validator(value) for key, value in validate.items()}

    def __call__(self, path: Path, obj: object) -> TypeGuard[dict[str, Any]]:  # noqa: ARG002
        if not (isinstance(obj, dict) and self.target_keys.issubset(obj)):
            return False

        return all(validator(obj[name]) for name, validator in self.validators.items())


def find_objs(
    value: object, *keys: str, validate: Mapping[str, Any] | None = None
) -> Generator[tuple[Path, dict[str, Any]]]:
    return traverse(value, DictVisitor(keys, validate))


def find_obj(value: object, *keys: str, validate: Mapping[str, Any] | None = None) -> tuple[Path, dict[str, Any]]:
    visitor = DictVisitor(keys, validate)
    with catch(f"object with keys = {sorted(visitor.target_keys)}"):
        return next(iter(traverse(value, visitor)))


def traverse_many(
    value: object, visitor: Visitor, *next_visitors: Visitor, path: Path = (), name: str | None = None
) -> TraverseResults[Path, Any]:
    return TraverseResults(_traverse_many(value, visitor, next_visitors, path=path), name=name)


def traverse_v2(
    value: object, cond: object, *next_conds: object, path: Path = (), name: str | None = None
) -> TraverseResults[Path, Any]:
    return traverse_many(
        value,
        value_visitor(cast_validator(cond)),
        *(value_visitor(cast_validator(cond)) for cond in next_conds),
        path=path,
        name=name,
    )
