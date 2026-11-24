from __future__ import annotations

import dataclasses
import itertools
import operator
from collections.abc import Callable, Generator, Iterable, Iterator, Mapping, Sequence
from typing import Any, Literal, TypeGuard, final

from typing_extensions import TypeIs, TypeVar

from cyberdrop_dl.constants import MISSING
from cyberdrop_dl.exceptions import ScrapeError

_T1 = TypeVar("_T1", default=Any)

type _TPath = tuple[str | int, ...]
type _Result[_T1] = tuple[bool, _T1]
type _Validator[_T1] = Callable[[object], _Result[_T1]]
type _VisitorCheck[_T1] = Callable[[_TPath, Any], _Result[_T1]]

__tracebackhide__ = True


@final
@dataclasses.dataclass(slots=True, frozen=True, eq=False)
class Visitor[T]:
    check: _VisitorCheck[T]
    branch_out: bool = False


@final
@dataclasses.dataclass(slots=True, frozen=True, eq=False)
class ValueVisitor[T, R]:
    # This is a class just to get a nice __repr__ with the inner func name
    fn: Callable[[T], R]

    def __call__(self, _: Any, value: T) -> R:
        return self.fn(value)


@final
@dataclasses.dataclass(slots=True, eq=False)
class TraverseResults[U]:
    _gen: Iterable[tuple[_TPath, U]]
    _count: int = dataclasses.field(init=False, default=0)

    def _walk(self) -> Iterator[tuple[_TPath, U]]:
        for path, value in self._gen:
            if type(value) is TraverseResults:
                for inner_path, inner_value in value:
                    yield (*path, *inner_path), inner_value
            else:
                yield path, value

    def __iter__(self) -> Iterator[tuple[_TPath, U]]:
        for pair in self._walk():
            self._count += 1
            yield pair

    def paths(self) -> Iterator[_TPath]:
        for path, _ in self:
            yield path

    def values(self) -> Iterator[U]:
        for _, value in self:
            yield value

    def _check_first(self) -> None:
        if self._count > 0:
            raise RuntimeError("We already yielded the first result")

    def get_value(self) -> U | None:
        return self.value(default=None)

    def value(self, name: str = "a required traverse attribute", *, default: Any = MISSING) -> U:
        self._check_first()
        for item in self.values():
            return item
        if default is MISSING:
            raise ScrapeError(422, f"Unable to find {name}")
        return default


def _traverse[T](value: object, visitor: Visitor[T], path: _TPath = ()) -> Generator[tuple[_TPath, T]]:
    matches, result = visitor.check(path, value)
    if matches:
        if type(result) is TraverseResults:
            for inner_path, inner_value in result:
                yield (*path, *inner_path), inner_value
        else:
            yield path, result

    elif visitor.branch_out:
        yield from _branch_out(value, visitor, path)


def _branch_out[T](value: object, visitor: Visitor[T], path: _TPath = ()) -> Generator[tuple[_TPath, T]]:
    match value:
        case dict():
            for key, item in value.items():
                yield from _traverse(item, visitor, (*path, key))

        case list() | tuple():
            for index, item in enumerate(value):
                yield from _traverse(item, visitor, (*path, index))

        case _:
            pass


def _force_branch_out(path: _TPath, value: Any) -> tuple[bool, Any]:
    visitor = Visitor(ValueVisitor(_cast_validator(None)), branch_out=False)
    return True, TraverseResults(_branch_out(value, visitor, path))


def _traverse_many[T](value: object, visitors: Sequence[Visitor[T]]) -> Iterable[tuple[_TPath, T]]:
    stack = [iter(_traverse(value, visitors[0]))]

    while stack:
        try:
            current_path, inner_value = next(stack[-1])
        except StopIteration:
            stack.pop()
            continue

        if len(stack) == len(visitors):
            yield current_path, inner_value
        else:
            stack.append(iter(_traverse(inner_value, visitors[len(stack)], current_path)))


def _is_class_info(obj: object) -> TypeGuard[type | tuple[type, ...]]:
    return isinstance(obj, type) or (type(obj) is tuple and all(isinstance(val, type) for val in obj))


def _transform_validator(fn: Callable[..., _T1]) -> _Validator[_T1]:

    def transform(inner_obj: Any):
        try:
            return True, fn(inner_obj)
        except Exception:  # noqa: BLE001
            return False, inner_obj

    return transform


def _filter_validator[T](fn: Callable[..., TypeIs[T] | T]) -> _Validator[T]:

    def check(inner_obj: Any):
        try:
            return bool(fn(inner_obj)), inner_obj
        except Exception:  # noqa: BLE001
            return False, inner_obj

    return check


def _set_validator(obj: set[object]) -> _Validator[Any]:
    if len(obj) != 1:
        raise ValueError("A set validator must have exactly 1 element")
    inner_obj = next(iter(obj))
    if _is_class_info(inner_obj):
        return _instance_validator(inner_obj)
    if callable(inner_obj):
        return _transform_validator(inner_obj)
    return _equals_validator(inner_obj)


def _instance_validator[T](obj: tuple[type[T], ...] | type[T]) -> _Validator[T]:
    def is_instance(inner_obj: object):
        return (isinstance(inner_obj, obj), inner_obj)

    return is_instance  # pyright: ignore[reportReturnType]


def _item_getter_validator(obj: str | int) -> _Validator[Any]:

    get = operator.itemgetter(obj)

    def get_item(inner_obj: Any):
        try:
            return True, get(inner_obj)
        except (LookupError, TypeError):
            return False, inner_obj

    return get_item


def _dict_validator(obj: Mapping[str, object]) -> _Validator[dict[str, _T1]]:
    validators: dict[str, list[Visitor[Any]]] = {k: _parse_visitors([cond]) for k, cond in obj.items()}

    def dict_getter(inner_obj: Any):
        if type(inner_obj) is not dict:
            return False, inner_obj

        if not validators.keys() <= inner_obj.keys():
            return False, inner_obj

        results = {}
        for name, visitors in validators.items():
            try:
                result = TraverseResults(_traverse_many(inner_obj[name], visitors)).value()
            except ScrapeError:
                return False, inner_obj
            else:
                results[name] = result

        return True, (inner_obj | results)

    return dict_getter


def _branch_all_validator(conds: list[Any]) -> _Validator[Any]:
    if not conds:
        raise ValueError("A branch out validator must have at least 1 condition")

    def branch_all(obj: Any):
        branches = [traverse(obj, cond) for cond in conds]
        return True, TraverseResults(itertools.chain.from_iterable(branches))

    return branch_all


def _chain_validator(conds: tuple[Any, ...]) -> _Validator[Any]:
    if not conds:
        raise ValueError("A chain validator must have at least 1 condition")

    visitors = _parse_visitors(conds)

    def chain(obj: Any):
        result = obj
        for visitor in visitors:
            try:
                result = TraverseResults(_traverse(result, visitor)).value()
            except ScrapeError:
                return False, None
        return True, result

    return chain


def _identity_visitor[T](obj: T) -> tuple[Literal[True], T]:
    return True, obj


def _equals_validator(obj: Any) -> _Validator[Any]:
    def equals(inner_obj: object):
        return (inner_obj == obj, inner_obj)

    return equals


def _cast_validator(cond: object) -> _Validator[Any]:
    if cond is None:
        return _identity_visitor

    if cond is filter:
        return _filter_validator(bool)

    match cond:
        case str() | int():
            val = _item_getter_validator(cond)
        case dict():
            val = _dict_validator(cond)
        case set():
            val = _set_validator(cond)
        case list():
            val = _branch_all_validator(cond)
        case tuple():
            val = _chain_validator(cond)
        case _:
            val = _filter_validator(cond) if callable(cond) else _equals_validator(cond)

    return val


def _parse_visitors(conds: list[Any] | tuple[Any, ...]) -> list[Visitor[Any]]:
    if not conds:
        raise ValueError("At least 1 condition must be provided")

    visitors: list[Visitor[Any]] = []
    branch_out = False
    for cond in conds:
        if cond is ...:
            if branch_out:
                visitors.append(Visitor(_force_branch_out, branch_out=False))
            else:
                branch_out = True
            continue

        if type(cond) is Visitor:
            branch_out = cond.branch_out or branch_out
            visitors.append(Visitor(cond.check, branch_out))

        else:
            visitors.append(Visitor(ValueVisitor(_cast_validator(cond)), branch_out))

        if branch_out:
            branch_out = False

    if branch_out:
        raise ValueError("A branch out condition must have another condition after it")

    if visitors[0].branch_out:
        visitors.insert(0, Visitor(_force_branch_out, branch_out=False))
    return visitors


def traverse(value: object, *conditions: object) -> TraverseResults[Any]:
    """traverse nested json data

    Inspired by yt-dlp's traverse_obj but using a very different (and intentionally simpler) implementation

    Behavior of conditions is similar but not exactly the same as yt-dlp's

    >>> obj = [{}, 12345, {"key": "john"}]
    >>> traverse(obj, 2, "key").value()
    'john'

    >>> traverse(obj, ..., "key").value()
    'john'

    >>> traverse(obj, ..., {"key": {int}}).value() # Raises ScrapeError

    >>> traverse(obj, ..., {"key": {int}}).get_value()
    None

    Only supports traversing objects supported by stdlib's json module:  list, tuple and dict (exact types, not subclasses)

    Conditions:

    - `None`:               Returns the current value as is

    - `set[<cond>]`:        It must have exactly 1 element. That element should be a type or a callable
                            If cond is class, it returns the current value if it passes an `isinstance` check.
                            If cond is a function, returns `func(obj)` if func does not raises any exception.
                            In any other case, returns obj  if `obj == <cond>`

    - `str` or `int`:       Returns `obj[key]`.

    - tuple[<cond>,...]     It must have at least 1 element. Elements can be any other valid condition.
                            Conditions will be chained.
                            The first result of the previous condition will be the input to the next.
                            If all conditions pass successfully, the last result will be returned

    - `list[<cond>]`:       It must have at least 1 element. Elements can be any other valid condition.
                            Conditions will branch out.
                            Yields results from all branches

    - `funtion (callable)`: Returns `value` if `function(value)` is truthy

    - `dict[str, <cond>]`:  Returns an obj if:
                            1: It's a `dict` (exact type)
                            2: Its keys are a subset of the declared keys
                            3: Their values match the conditions.

    - `...` (Ellipsis):     Branch out and yield values from all branches that match the next condition.
                            It MUST have a condition after it
                            Use 2 of them to force a branch out ignoring the current object
                            The root obj is always ignored if the first traverse condition is ...

    - `filter` (built-in):  Return the value if it is truthy.

    Any other object not listed above used as condition will return value if value == <cond>
    """

    visitors = _parse_visitors(conditions)
    return TraverseResults(_traverse_many(value, visitors))
