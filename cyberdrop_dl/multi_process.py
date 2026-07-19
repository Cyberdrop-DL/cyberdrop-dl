from __future__ import annotations

import contextlib
import dataclasses
import os
import sys
from contextvars import ContextVar
from typing import TYPE_CHECKING, Concatenate

from cyberdrop_dl.utils import enter_context

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

_TIMEOUT: ContextVar[float] = ContextVar("_Timeout", default=30.0)
_MAX_WORKERS: ContextVar[int | None] = ContextVar("_MAX_WORKERS", default=None)


@dataclasses.dataclass(slots=True)
class PowResult[T]:
    value: T
    elapsed: float


@contextlib.contextmanager
def ctx(max_workers: int | None = None, timeout: float = 30.0) -> Generator[None]:
    with enter_context(_MAX_WORKERS, max_workers), enter_context(_TIMEOUT, timeout):
        yield


def race[**P, R](
    worker: Callable[Concatenate[int, int, P], R | None], *args: P.args, **kwargs: P.kwargs
) -> PowResult[R]:
    """Execute a worker function across multiple processes in a race condition, returning the first non-None result.

    All other processes are cancelled on exit.
    """
    import multiprocessing as mp
    import time
    from concurrent.futures import ProcessPoolExecutor, as_completed

    cpu_limit = max(cpu_count() // 2, 1)
    max_workers = _MAX_WORKERS.get()
    max_workers = cpu_limit if not max_workers else min(max_workers, cpu_limit)
    start_time = time.monotonic()

    with ProcessPoolExecutor(max_workers=max_workers, mp_context=mp.get_context("spawn")) as executor:
        futures = [executor.submit(worker, idx, max_workers, *args, **kwargs) for idx in range(max_workers)]

        for future in as_completed(futures, timeout=_TIMEOUT.get()):
            result = future.result()
            if result is not None:
                elapsed = time.monotonic() - start_time
                executor.shutdown(wait=False, cancel_futures=True)
                return PowResult(result, elapsed)

    raise RuntimeError


if sys.platform not in {"win32", "darwin"} and hasattr(os, "sched_getaffinity"):

    def cpu_count() -> int:
        return len(os.sched_getaffinity(0))


else:

    def cpu_count() -> int:
        return os.cpu_count() or 1
