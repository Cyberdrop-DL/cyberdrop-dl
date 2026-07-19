from __future__ import annotations

import contextlib
import dataclasses
import os
import sys
from contextvars import ContextVar
from typing import TYPE_CHECKING, Concatenate

from cyberdrop_dl import aio
from cyberdrop_dl.constants import MISSING
from cyberdrop_dl.utils import enter_context

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

TIMEOUT: ContextVar[float | None] = ContextVar("TIMEOUT", default=30.0)
MAX_WORKERS: ContextVar[int | None] = ContextVar("MAX_WORKERS", default=None)


@dataclasses.dataclass(slots=True)
class RaceResult[T]:
    value: T
    elapsed: float
    workers: int


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


def race[**P, R](
    worker: Callable[Concatenate[int, int, P], R | None], *args: P.args, **kwargs: P.kwargs
) -> RaceResult[R]:
    """Execute a worker function across multiple processes in a race condition, returning the first non-None result.

    All other processes are cancelled on exit.
    """
    import multiprocessing as mp
    import time
    from concurrent.futures import ProcessPoolExecutor, as_completed

    cpu_limit = max(cpu_count() // 2, 1)
    max_workers = MAX_WORKERS.get()
    max_workers = cpu_limit if not max_workers else min(max_workers, cpu_limit)
    start_time = time.monotonic()

    with ProcessPoolExecutor(max_workers=max_workers, mp_context=mp.get_context("spawn")) as executor:
        futures = [executor.submit(worker, idx, max_workers, *args, **kwargs) for idx in range(max_workers)]

        for future in as_completed(futures, timeout=TIMEOUT.get()):
            result = future.result()
            if result is not None:
                elapsed = time.monotonic() - start_time
                executor.shutdown(wait=False, cancel_futures=True)
                return RaceResult(result, elapsed, max_workers)

    raise RuntimeError("None of the workers found a solution")


async_race = aio.to_thread(race)

if sys.platform not in {"win32", "darwin"} and hasattr(os, "sched_getaffinity"):

    def cpu_count() -> int:
        return len(os.sched_getaffinity(0))


else:

    def cpu_count() -> int:
        return os.cpu_count() or 1
