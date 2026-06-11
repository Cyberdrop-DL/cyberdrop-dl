"""Async versions of builtins and some path operations"""

# ruff: noqa: A001
from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import functools
import shutil
import tempfile
import time
from pathlib import Path
from stat import S_ISREG
from typing import IO, TYPE_CHECKING, Any, AnyStr, Self, cast, overload
from weakref import WeakValueDictionary

from aiolimiter.leakybucket import AsyncLimiter
from typing_extensions import Sentinel

if TYPE_CHECKING:
    from collections.abc import (
        AsyncGenerator,
        AsyncIterable,
        AsyncIterator,
        Awaitable,
        Callable,
        Coroutine,
        Iterable,
        Iterator,
        Sequence,
    )
    from types import CoroutineType

    from _typeshed import OpenBinaryMode, OpenTextMode


_MISSING = Sentinel("_MISSING")


class _AsyncChain:
    """Like itertools.chain, but for async iterables"""

    def __repr__(self) -> str:
        return f"{type(self).__name__}"

    def __call__[T](self, *async_iterables: AsyncIterable[T]) -> AsyncGenerator[T]:
        return self.from_iterable(async_iterables)

    @staticmethod
    async def from_iterable[T](async_iterables: Iterable[AsyncIterable[T]]) -> AsyncGenerator[T]:
        for a_iterable in async_iterables:
            async for value in a_iterable:
                yield value


chain = _AsyncChain()


async def peek_first[T](async_iterable: AsyncIterable[T], /) -> tuple[T, AsyncGenerator[T, None]]:
    async_iterator = aiter(async_iterable)
    try:
        first = await anext(async_iterator)
    except StopAsyncIteration as e:
        raise e.__cause__ or e from None

    async def yield_again() -> AsyncGenerator[T, None]:
        yield first

    return first, chain(yield_again(), async_iterator)


@dataclasses.dataclass(slots=True, eq=False)
class WeakAsyncLocks[T]:
    """A WeakValueDictionary wrapper for asyncio.Locks.

    Unused locks are automatically garbage collected. When trying to retrieve a
    lock that does not exists, a new lock will be created.
    """

    _locks: WeakValueDictionary[T, asyncio.Lock] = dataclasses.field(init=False, default_factory=WeakValueDictionary)

    def __getitem__(self, key: T, /) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            self._locks[key] = lock = asyncio.Lock()
        return lock


class RateLimiter(AsyncLimiter):
    __slots__ = ()

    async def acquire(self, amount: float = 1) -> None:
        if self.max_rate == 0:
            return
        await super().acquire(amount)

    @classmethod
    def w_no_burst(cls, max_rate: float, time_period: float = 1) -> Self:
        """Create a new instance that prevents acquisitions from bursting through the limit.

        Instead of allowing up to <max_rate> acquisitions over a period of <time_period>,
        spread them evenly across the <time_period> to maintain a steady rate of <max_rate>.
        """
        if max_rate == 0:
            return cls.no_op()
        return cls(max_rate=1, time_period=time_period / max_rate)

    @classmethod
    def no_op(cls) -> Self:
        return cls(max_rate=0, time_period=1)


@dataclasses.dataclass(slots=True, frozen=True)
class _CachedValue[T]:
    value: T
    ttl: float
    created_at: float = dataclasses.field(init=False, default_factory=time.monotonic)

    @property
    def has_expired(self) -> bool:
        return time.monotonic() - self.created_at >= self.ttl


def cache_wrapper[T](
    *, ttl: float | None = None
) -> Callable[[Callable[[], Awaitable[T]]], Callable[[], CoroutineType[Any, Any, T]]]:

    return lambda x: cached(x, ttl=ttl)


def cached[T](fn: Callable[[], Awaitable[T]], *, ttl: float | None = None) -> Callable[[], CoroutineType[Any, Any, T]]:
    if ttl is None:
        return _perpetual_cache(fn)

    lock = asyncio.Lock()
    cached_value: _CachedValue[T] | None = None

    @functools.wraps(fn)
    async def wrapper() -> T:
        nonlocal cached_value
        async with lock:
            if cached_value is not None and not cached_value.has_expired:
                return cached_value.value

            cached_value = _CachedValue(await fn(), ttl=ttl)

        return cached_value.value

    return wrapper


def _perpetual_cache[T](fn: Callable[[], Awaitable[T]]) -> Callable[[], CoroutineType[Any, Any, T]]:
    lock = asyncio.Lock()
    cached_value: T | Sentinel = _MISSING

    @functools.wraps(fn)
    async def wrapper() -> T:
        nonlocal cached_value
        if cached_value is not _MISSING:
            return cast("T", cached_value)

        async with lock:
            if cached_value is not _MISSING:
                return cast("T", cached_value)

            cached_value = await fn()

        return cached_value

    return wrapper


@dataclasses.dataclass(slots=True, eq=False)
class AsyncIOWrapper[AnyStr: (bytes, str)]:
    """An asynchronous context manager wrapper for a file object."""

    _coro: Awaitable[IO[AnyStr]]
    _io: IO[AnyStr] = dataclasses.field(init=False)

    async def __aenter__(self) -> Self:
        self._io = await self._coro
        return self

    async def __aexit__(self, *_: object) -> None:
        return await asyncio.to_thread(self._io.close)

    async def __aiter__(self) -> AsyncIterator[AnyStr]:
        while True:
            line = await self.readline()
            if line:
                yield line
            else:
                break

    async def read(self, size: int = -1) -> AnyStr:
        return await asyncio.to_thread(self._io.read, size)

    async def readline(self) -> AnyStr:
        return await asyncio.to_thread(self._io.readline)

    async def readlines(self) -> list[AnyStr]:
        return await asyncio.to_thread(self._io.readlines)

    async def write(self, b: AnyStr, /) -> int:
        return await asyncio.to_thread(self._io.write, b)

    async def writelines(self, lines: Iterable[AnyStr], /) -> None:
        return await asyncio.to_thread(self._io.writelines, lines)


@dataclasses.dataclass(slots=True, eq=False)
class AsyncIteratorWrapper[T]:
    _coro: Awaitable[Iterable[T]]
    _iterator: Iterator[T] | None = dataclasses.field(default=None, init=False)

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> T:
        if self._iterator is None:
            self._iterator = iter(await self._coro)
        value = await asyncio.to_thread(next, self._iterator, _MISSING)
        if value is _MISSING:
            raise StopAsyncIteration from None

        return cast("T", value)


async def gather[T](*coros: Awaitable[T]) -> list[T]:
    """Like asyncio.gather but an exception on any coro cancels all pending coros

    AKA: all or nothing"""

    async def wrap(coro: Awaitable[T]) -> T:
        return await coro

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(wrap(coro)) for coro in coros]

    return [t.result() for t in tasks]


@overload
async def safe_gather[T1](coro: Awaitable[T1], /) -> tuple[T1]: ...
@overload
async def safe_gather[T1, T2](coro_1: Awaitable[T1], coro_2: Awaitable[T2], /) -> tuple[T1, T2]: ...
@overload
async def safe_gather[T1, T2, T3](
    coro_1: Awaitable[T1],
    coro_2: Awaitable[T2],
    coro_3: Awaitable[T3],
    /,
) -> tuple[T1, T2, T3]: ...


async def safe_gather[T1, T2, T3](
    coro_1: Awaitable[T1],
    coro_2: Awaitable[T2] | None = None,
    coro_3: Awaitable[T3] | None = None,
    /,
) -> Sequence[T1 | T2 | T3]:
    """Like `asyncio.gather(*coros, return_exceptions=True)`, but all exceptions are re-raised as an ExceptionGroup

    This makes errors deterministic"""

    coros = filter(None, (coro_1, coro_2, coro_3))
    results = await asyncio.gather(*coros, return_exceptions=True)
    errors = tuple(r for r in results if isinstance(r, BaseException))
    if errors:
        raise BaseExceptionGroup("", errors)
    return cast("list[T1 | T2 | T3]", results)


async def map[T, R](
    coro_factory: Callable[[T], Awaitable[R]],
    params: Iterable[T],
    /,
    *,
    task_limit: asyncio.BoundedSemaphore | int | None,
) -> list[R]:
    """Map an async factory over a sequence of arguments with optional concurrency cap.

    If `task_limit` is given, no more than that many coroutines will be “in flight” at the same time,
    limiting memory pressure and event loop overhead"""
    return await map_tuples(coro_factory, ((param,) for param in params), task_limit=task_limit)


async def map_tuples[*Ts, R](
    coro_factory: Callable[[*Ts], Awaitable[R]],
    params_batched: Iterable[tuple[*Ts]],
    /,
    *,
    task_limit: asyncio.BoundedSemaphore | int | None = None,
) -> list[R]:
    """Map an async factory over a sequence of arguments with optional concurrency cap.

    If `task_limit` is given, no more than that many coroutines will be “in flight” at the same time,
    limiting memory pressure and event loop overhead"""
    if not task_limit:
        return await gather(*(coro_factory(*params) for params in params_batched))

    semaphore = asyncio.BoundedSemaphore(task_limit) if isinstance(task_limit, int) else task_limit

    tasks: list[asyncio.Task[R]] = []

    async def run(coro: Awaitable[R]) -> R:
        try:
            return await coro
        finally:
            semaphore.release()

    async with asyncio.TaskGroup() as tg:
        for params in params_batched:
            _ = await semaphore.acquire()
            coro = coro_factory(*params)
            tasks.append(tg.create_task(run(coro)))

    return [t.result() for t in tasks]


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    def loop_factory() -> asyncio.AbstractEventLoop:
        loop = asyncio.new_event_loop()
        loop.set_task_factory(asyncio.eager_task_factory)
        return loop

    with asyncio.Runner(loop_factory=loop_factory) as runner:
        return runner.run(coro)


def to_thread[**P, R](fn: Callable[P, R]) -> Callable[P, Coroutine[None, None, R]]:
    """Convert a blocking callable into an async callable that runs in another thread"""

    async def async_run(*args: P.args, **kwargs: P.kwargs) -> R:
        return await asyncio.to_thread(fn, *args, **kwargs)

    return async_run


chmod = to_thread(Path.chmod)
copy = to_thread(shutil.copy)
exists = to_thread(Path.exists)
is_dir = to_thread(Path.is_dir)
is_file = to_thread(Path.is_file)
mkdir = to_thread(Path.mkdir)
move = to_thread(shutil.move)
read_bytes = to_thread(Path.read_bytes)
read_text = to_thread(Path.read_text)
resolve = to_thread(Path.resolve)
stat = to_thread(Path.stat)
touch = to_thread(Path.touch)
unlink = remove = to_thread(Path.unlink)
write_bytes = to_thread(Path.write_bytes)
write_text = to_thread(Path.write_text)
rmdir = to_thread(Path.rmdir)


def glob(path: Path, pattern: str) -> AsyncIterator[Path]:
    coro = asyncio.to_thread(path.glob, pattern)
    return AsyncIteratorWrapper(coro)


def rglob(path: Path, pattern: str) -> AsyncIterator[Path]:
    coro = asyncio.to_thread(path.rglob, pattern)
    return AsyncIteratorWrapper(coro)


def iterdir(path: Path) -> AsyncIterator[Path]:
    coro = asyncio.to_thread(path.iterdir)
    return AsyncIteratorWrapper(coro)


@overload
def open(
    path: Path,
    mode: OpenBinaryMode,
    buffering: int = ...,
    encoding: str | None = ...,
    errors: str | None = ...,
    newline: str | None = ...,
) -> AsyncIOWrapper[bytes]: ...


@overload
def open(
    path: Path,
    mode: OpenTextMode = ...,
    buffering: int = ...,
    encoding: str | None = ...,
    errors: str | None = ...,
    newline: str | None = ...,
) -> AsyncIOWrapper[str]: ...


def open(  # noqa: PLR0913
    path: Path,
    mode: str = "r",
    buffering: int = -1,
    encoding: str | None = None,
    errors: str | None = None,
    newline: str | None = None,
) -> AsyncIOWrapper[Any]:
    coro = asyncio.to_thread(path.open, mode, buffering, encoding, errors, newline)
    return AsyncIOWrapper(coro)


async def get_size(path: Path) -> int | None:
    """If path exists and is a file, returns its size. Returns `None` otherwise"""

    # Manually parse stat result to make sure we only use 1 fs call

    try:
        stat_result = await stat(path)
    except (OSError, ValueError):
        return None
    else:
        if not S_ISREG(stat_result.st_mode):
            raise IsADirectoryError(path)
        return stat_result.st_size


@contextlib.asynccontextmanager
async def temp_dir() -> AsyncGenerator[Path]:
    temp_dir = await asyncio.to_thread(tempfile.TemporaryDirectory, prefix="cdl_", ignore_cleanup_errors=True)
    try:
        yield Path(temp_dir.name)
    finally:
        await asyncio.to_thread(temp_dir.cleanup)


def periodic_sleep(period: int, /) -> Callable[[], Awaitable[None]]:
    """Yield control to the event loop every n calls

    To use within busy blocking loops"""

    if period <= 0:
        raise ValueError("period must be a positive integer")

    calls = 0

    async def sleep() -> None:
        nonlocal calls
        calls += 1
        if calls % period == 0:
            await asyncio.sleep(0)

    return sleep
