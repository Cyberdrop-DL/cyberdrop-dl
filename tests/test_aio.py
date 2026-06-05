from __future__ import annotations

import asyncio

from cyberdrop_dl import aio


class Spy:
    def __init__(self, value: object) -> None:
        self.value: object = value
        self.calls: int = 0

    async def __call__(self) -> object:
        self.calls += 1
        return self.value


async def test_cache_returns_same_value_while_not_expired() -> None:
    ttl = 2.0
    spy = Spy("test 1")
    factory = aio.cache_wrapper(ttl=ttl)(spy)
    first = await factory()
    second = await factory()

    assert first == second
    assert spy.calls == 1
    await asyncio.sleep(ttl + 0.1)
    _ = await factory()
    assert spy.calls == 2


async def test_concurrent_calls_execute_only_once() -> None:
    spy = Spy("test 2")

    @aio.cache_wrapper(ttl=60)
    async def factory() -> object:
        await asyncio.sleep(0.02)
        return await spy()

    results = await asyncio.gather(*(factory() for _ in range(10)))
    assert len(set(results)) == 1
    assert spy.calls == 1
