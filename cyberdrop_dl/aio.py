"""Async versions of builtins and some path operations"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import shutil
import sys
import tempfile
from pathlib import Path
from stat import S_ISREG
from typing import IO, TYPE_CHECKING, Any, AnyStr, Generic, ParamSpec, Self, TypeVar, TypeVarTuple, cast, overload
from weakref import WeakValueDictionary

from aiolimiter.leakybucket import AsyncLimiter
from typing_extensions import Sentinel

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Coroutine, Iterable, Iterator

    from _typeshed import OpenBinaryMode, OpenTextMode


_T = TypeVar("_T")
_Ts = TypeVarTuple("_Ts")
_R = TypeVar("_R")
_P = ParamSpec("_P")
_MISSING = Sentinel("_MISSING")


@dataclasses.dataclass(slots=True, eq=False)
class WeakAsyncLocks(Generic[_T]):
    """A WeakValueDictionary wrapper for asyncio.Locks.

    Unused locks are automatically garbage collected. When trying to retrieve a
    lock that does not exists, a new lock will be created.
    """

    _locks: WeakValueDictionary[_T, asyncio.Lock] = dataclasses.field(init=False, default_factory=WeakValueDictionary)

    def __getitem__(self, key: _T, /) -> asyncio.Lock:
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


@dataclasses.dataclass(slots=True, eq=False)
class AsyncIOWrapper(Generic[AnyStr]):
    """An asynchronous context manager wrapper for a file object."""

    _coro: Awaitable[IO[AnyStr]]
    _io: IO[AnyStr] = dataclasses.field(init=False)

    async def __aenter__(self) -> Self:
        self._io = await self._coro
        return self

    async def __aexit__(self, *_) -> None:
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
class AsyncIteratorWrapper(Generic[_T]):
    _coro: Awaitable[Iterable[_T]]
    _iterator: Iterator[_T] | None = dataclasses.field(default=None, init=False)

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> _T:
        if self._iterator is None:
            self._iterator = iter(await self._coro)
        value = await asyncio.to_thread(next, self._iterator, _MISSING)
        if value is _MISSING:
            raise StopAsyncIteration from None

        return cast("_T", value)


async def gather(*coros: Awaitable[_T]) -> list[_T]:
    """Like asyncio.gather but an exception on any coro cancels all pending coros

    AKA: all or nothing"""

    async def run(coro: Awaitable[_R]) -> _R:
        return await coro

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(run(coro)) for coro in coros]

    return [t.result() for t in tasks]


async def map(
    coro_factory: Callable[[_T], Awaitable[_R]],
    params: Iterable[_T],
    /,
    *,
    task_limit: int | None = None,
) -> list[_R]:
    """Map an async factory over a sequence of arguments with optional concurrency cap.

    If `task_limit` is given, no more than that many coroutines will be “in flight” at the same time,
    limiting memory pressure and event loop overhead"""
    return await map_tuples(coro_factory, ((param,) for param in params), task_limit=task_limit)


async def map_tuples(
    coro_factory: Callable[[*_Ts], Awaitable[_R]],
    params_batched: Iterable[tuple[*_Ts]],
    /,
    *,
    task_limit: int | None = None,
) -> list[_R]:
    """Map an async factory over a sequence of arguments with optional concurrency cap.

    If `task_limit` is given, no more than that many coroutines will be “in flight” at the same time,
    limiting memory pressure and event loop overhead"""
    if not task_limit:
        return await gather(*(coro_factory(*params) for params in params_batched))

    semaphore = asyncio.BoundedSemaphore(task_limit)
    tasks: list[asyncio.Task[_R]] = []

    async def run(coro: Awaitable[_R]) -> _R:
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


def run(coro: Coroutine[Any, Any, _T]) -> _T:
    def _loop_factory() -> asyncio.AbstractEventLoop:
        loop = asyncio.new_event_loop()
        if sys.version_info > (3, 12):
            loop.set_task_factory(asyncio.eager_task_factory)
        return loop

    with asyncio.Runner(loop_factory=_loop_factory) as runner:
        return runner.run(coro)


def to_thread(fn: Callable[_P, _R]) -> Callable[_P, Coroutine[None, None, _R]]:
    """Convert a blocking callable into an async callable that runs in another thread"""

    async def async_run(*args: _P.args, **kwargs: _P.kwargs) -> _R:
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


def open(
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
        return
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
