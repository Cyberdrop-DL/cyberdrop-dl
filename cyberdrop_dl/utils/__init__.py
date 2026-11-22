from __future__ import annotations

import itertools
import logging
import operator
import sys
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, cast, overload

from cyberdrop_dl.constants import MISSING
from cyberdrop_dl.exceptions import ScrapeError

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable, Iterator


logger = logging.getLogger(__name__)


def extract_text(text: str, /, start: str, end: str, pos: int | None = None) -> tuple[int, str]:
    """Extracts the text between two strings in a larger text.

    Result will be stripped"""
    start_index = text.index(start, pos) + len(start)
    end_index = text.index(end, start_index)
    return end_index + len(end), text[start_index:end_index].strip()


def extr_text(text: str, /, start: str, end: str) -> str:
    """Extracts the text between two strings in a larger text.

    Result will be stripped"""
    _, txt = extract_text(text, start, end)
    return txt


class TextExtractor:
    def __init__(self, text: str, /, pos: int | None = None) -> None:
        self.text: str = text
        self.cursor: int | None = pos

    def __repr__(self) -> str:
        return f"{type(self).__name__}(text={self.text!r}, cursor={self.cursor!r})"

    def __call__(self, start: str, end: str) -> str:
        self.cursor, txt = extract_text(self.text, start, end, self.cursor)
        return txt

    def repeat(self, start: str, end: str) -> Generator[str]:
        while True:
            try:
                yield self(start, end)
            except ValueError:
                return


def get_system_information() -> dict[str, Any]:
    import platform
    import sqlite3
    import ssl

    import certifi
    import wassima

    def get_common_name() -> str:
        system = platform.system()

        if system == "Linux":
            try:
                return platform.freedesktop_os_release()["PRETTY_NAME"]
            except OSError:
                pass

        if system == "Android" and sys.version_info >= (3, 13):
            ver = platform.android_ver()
            os_name = f"{system} {ver.release}"
            for component in (ver.manufacturer, ver.model, ver.device):
                if component:
                    os_name += f" ({component})"
            return os_name

        default = platform.platform(aliased=True, terse=True).replace("-", " ")
        if system == "Windows" and (edition := platform.win32_edition()):
            return f"{default} {edition}"
        return default

    system_info = (
        {
            "prefix": sys.prefix,
            "executable": sys.executable,
            "GIL enabled": sys._is_gil_enabled() if sys.version_info >= (3, 13) else True,
        }
        | platform.uname()._asdict()
        | {
            "architecture": str(platform.architecture()),
            "python": f"{platform.python_version()} {platform.python_implementation()}",
            "common_name": get_common_name(),
            "sqlite": sqlite3.sqlite_version,
            "certifi": certifi.__version__,
            "wassima": wassima.__version__,
            "openSSL": ssl.OPENSSL_VERSION,
        }
    )
    _ = system_info.pop("node", None)
    return system_info


def is_blob_or_svg(link: str) -> bool:
    return link.startswith(("data:", "blob:", "javascript:"))


def xor_decrypt(encrypted_data: bytes, key: bytes) -> str:
    data = bytearray(b_input ^ b_key for b_input, b_key in zip(encrypted_data, itertools.cycle(key)))
    return data.decode("utf-8", errors="ignore")


def truncated_preview(content: str, max_len: int = 100) -> str:
    if len(content) <= max_len:
        return content
    return f"{content[:max_len]} ... ({len(content) - max_len:,} chars omitted)"


def basic_auth(username: str, password: str) -> str:
    import base64

    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return f"Basic {token}"


def fast_cache[T, R](fn: Callable[[T], R]) -> Callable[[T], R]:
    """Like functools.cache but for single argument function and without all the stats logic

    cache never expires"""
    cache: dict[T, R] = {}

    def compute(obj: T) -> R:
        val = cache.get(obj, MISSING)
        if val is not MISSING:
            return cast("R", val)

        cache[obj] = val = fn(obj)
        return val

    return compute


def b64_pad(b64_string: str) -> str:
    if pad := len(b64_string) % 4:
        return b64_string + "=" * (4 - pad)
    return b64_string


type AnythingButTupleOrList = (
    str
    | bytes
    | int
    | float
    | Mapping[Any, Any]
    | set[Any]
    | frozenset[Any]
    | bool
    | range
    | Callable[..., Any]
    | BaseException
    | type
)


@overload
def strict_variadic[T: AnythingButTupleOrList](value: T) -> tuple[T, ...]: ...


@overload
def strict_variadic[T: AnythingButTupleOrList](value: tuple[T, ...]) -> tuple[T, ...]: ...


@overload
def strict_variadic[T: AnythingButTupleOrList](value: list[T]) -> list[T]: ...


@overload
def strict_variadic[T: tuple[Any, ...]](value: T) -> T: ...


def strict_variadic(value: Any) -> tuple[Any, ...] | list[Any]:
    if type(value) in {tuple, list}:
        return value
    return (value,)


class Deduper[R]:
    def __init__(self, get_key: Callable[[Any], R] | None = None) -> None:
        self.seen: set[R] = set()
        self.get_key: Callable[[Any], R] = get_key if get_key is not None else lambda x: x

    def __contains__(self, obj: Any) -> bool:
        lookup = self.get_key(obj)
        if lookup in self.seen:
            return True
        self.seen.add(lookup)
        return False

    def __len__(self) -> int:
        return len(self.seen)

    def __iter__(self) -> Iterator[R]:
        return iter(self.seen)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(seen={self.seen!r})"

    def clear(self) -> None:
        return self.seen.clear()

    def filter[Z](self, items: Iterable[Z]) -> Iterable[Z]:
        for item in items:
            if item not in self:
                yield item

    @classmethod
    def by_attr(cls, attr: str) -> Self:
        return cls(operator.attrgetter(attr))


def unique[T](itr: Iterable[T], /, key: Callable[[T], Any] | None = None) -> Iterable[T]:
    if key is None:
        return dict.fromkeys(itr).keys()
    return Deduper(key).filter(itr)


def next_or_error[T](itr: Iterable[T], name: str) -> T:
    for item in itr:
        return item
    raise ScrapeError(422, f"Unable to find {name}")


def catch[**P, R](
    fn: Callable[P, R], exc: tuple[type[Exception], ...] | type[Exception] = Exception
) -> Callable[P, R | None]:

    def call(*args: P.args, **kwargs: P.kwargs) -> R | None:
        try:
            return fn(*args, **kwargs)
        except exc:
            return None

    return call


def remove_quotes(string: str) -> str:
    if len(string) > 1:
        start, end = string[0], string[-1]
        if start in {"'", '"'} and start == end:
            return string[1:-1]
    return string
