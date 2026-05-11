import asyncio
import time

import pytest

from cyberdrop_dl.aio import RateLimiter


async def consume(limiter: RateLimiter, iterations: int) -> list[float]:
    times: list[float] = []
    for _ in range(iterations):
        await limiter.acquire()
        times.append(time.perf_counter())
    return times


async def test_no_op_never_throttles() -> None:
    limiter = RateLimiter.no_op()
    assert limiter.max_rate == 0
    start = time.perf_counter()
    # calls should pretty much return instantly
    await asyncio.gather(*(limiter.acquire() for _ in range(1_000)))
    delta = time.perf_counter() - start
    assert delta < 0.05


async def test_w_no_burst_zero_rate() -> None:
    limiter = RateLimiter.w_no_burst(0)
    assert limiter.max_rate == 0
    assert limiter.time_period == 1


async def test_w_no_burst_spreads_evenly() -> None:
    """10 req/s should yield about 0.1s spacing inbetween calls."""
    limiter = RateLimiter.w_no_burst(max_rate=10, time_period=1)
    n_calls = 10
    times = await consume(limiter, n_calls)
    deltas = [times[i + 1] - times[i] for i in range(n_calls - 1)]
    for delta in deltas:
        assert delta == pytest.approx(0.1, rel=0.3)


async def test_default_contructor_allows_burst() -> None:
    max_rate = 20
    limiter = RateLimiter(max_rate, time_period=1)
    start = time.perf_counter()
    await asyncio.gather(*(limiter.acquire() for _ in range(max_rate)))
    delta = time.perf_counter() - start
    assert delta < 0.002


async def test_acquire_when_bucket_is_full() -> None:
    max_rate = 2
    expected_delta = 1 / max_rate
    limiter = RateLimiter(max_rate, time_period=1)
    start = time.perf_counter()
    await limiter.acquire(max_rate)
    assert time.perf_counter() - start < 0.001
    await limiter.acquire(1)
    delta = time.perf_counter() - start
    assert delta == pytest.approx(expected_delta, rel=0.3)
