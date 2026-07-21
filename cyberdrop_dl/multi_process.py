from __future__ import annotations

import concurrent.futures
import contextlib
import dataclasses
import multiprocessing as mp
import os
import sys
import time
from contextvars import ContextVar
from typing import TYPE_CHECKING, Concatenate

from cyberdrop_dl.constants import MISSING
from cyberdrop_dl.utils import enter_context

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable

TIMEOUT: ContextVar[float | None] = ContextVar("TIMEOUT", default=30.0)
MAX_WORKERS: ContextVar[int | None] = ContextVar("MAX_WORKERS", default=None)


class PoolExecutor(concurrent.futures.ProcessPoolExecutor):
    @property
    def workers(self) -> int:
        return len(self._processes)

    @property
    def max_workers(self) -> int:
        return self._max_workers  # pyright: ignore[reportAttributeAccessIssue]

    def __init__(self) -> None:
        cpu_limit = max(cpu_count() // 2, 1)
        max_workers = MAX_WORKERS.get()
        super().__init__(
            max_workers=cpu_limit if not max_workers else min(max_workers, cpu_limit),
            mp_context=mp.get_context("spawn"),
        )


@dataclasses.dataclass(slots=True)
class RaceResult[T]:
    value: T
    elapsed: float


@contextlib.contextmanager
def ctx(
    max_workers: int | None | MISSING = MISSING,  # pyright: ignore[reportInvalidTypeForm]
    timeout: float | None | MISSING = MISSING,  # pyright: ignore[reportInvalidTypeForm]
) -> Generator[None]:
    with contextlib.ExitStack() as stack:
        if max_workers is not MISSING:
            stack.enter_context(enter_context(MAX_WORKERS, max_workers))
        if timeout is not MISSING:
            stack.enter_context(enter_context(TIMEOUT, timeout))
        yield


def inject_timeout[**P, T, R](
    func: Callable[Concatenate[Iterable[concurrent.futures.Future[T]], float | None, P], R],
) -> Callable[Concatenate[Iterable[concurrent.futures.Future[T]], P], R]:

    def wrapper(futures: Iterable[concurrent.futures.Future[T]], *args: P.args, **kwargs: P.kwargs) -> R:
        return func(futures, TIMEOUT.get(), *args, **kwargs)

    return wrapper


as_completed = inject_timeout(concurrent.futures.as_completed)
wait = inject_timeout(concurrent.futures.wait)


def wait_for_one[T](futures: Iterable[concurrent.futures.Future[T]], /) -> concurrent.futures.Future[T]:
    new_futs = wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
    return next(iter(new_futs.done))


def race[**P, R](worker: Callable[Concatenate[int, int, P], R], *args: P.args, **kwargs: P.kwargs) -> RaceResult[R]:
    """Execute a worker function across multiple processes, returning the first one to complete.

    Worker id and max workers are injected as the first arguments to the worker. They should be useded as seeds.

    All processes are cancelled on exit.
    """

    start_time = time.monotonic()
    executor = PoolExecutor()
    try:
        futures = (
            executor.submit(worker, idx, executor.max_workers, *args, **kwargs) for idx in range(executor.max_workers)
        )
        result = wait_for_one(futures).result()
        elapsed = time.monotonic() - start_time
        return RaceResult(result, elapsed)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


if sys.platform not in {"win32", "darwin"} and hasattr(os, "sched_getaffinity"):

    def cpu_count() -> int:
        return len(os.sched_getaffinity(0))


else:

    def cpu_count() -> int:
        return os.cpu_count() or 1
