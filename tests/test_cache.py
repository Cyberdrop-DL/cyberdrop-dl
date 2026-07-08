import asyncio
import time
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from cyberdrop_dl import __version__
from cyberdrop_dl.cache import (
    _IN_MEMORY_CACHE,
    TTLCacheAdapter,
    _DiskCachedMethod,
    _normalize_key,
    cache_context,
    cached_fn,
    disk_cached_method,
)
from cyberdrop_dl.config.appdata import AppData
from cyberdrop_dl.manager import Manager
from cyberdrop_dl.utils import json


def test_cache_file_is_not_saved_outside_ctx(appdata: AppData) -> None:
    manager = Manager(appdata=appdata)
    cache_file = manager.appdata.cache_file
    manager.cache["test"] = 1
    assert manager.cache == {"test": 1}
    assert not cache_file.exists()


def test_cache_file_is_saved_in_ctx(tmp_path: Path) -> None:
    cache_file = tmp_path / "cache_file.txt"
    cache: dict[str, Any] = {}
    with cache_context(cache_file, cache):
        cache["test"] = 1
        assert cache == {"test": 1}
        assert cache_file.is_file()

    assert cache_file.is_file()
    assert json.loads(cache_file.read_text()) == {"test": 1, "version": __version__}


def test_ttl_cache_creation() -> None:
    cache = {}
    ttl_cache = TTLCacheAdapter(cache, ("a", "b"))
    assert cache == {}
    assert ttl_cache.get("account") is None
    assert cache == {"a": {"b": {}}}


def test_ttl_cache_add() -> None:
    cache = {}
    ttl_cache = TTLCacheAdapter(cache, ("a", "b"))
    assert ttl_cache._lookup_path("account") == "a.b.account"
    ttl_cache.save("account", 123, ttl=60)
    assert cache == {
        "a": {
            "b": {
                "account": {
                    "value": 123,
                    "ttl": 60,
                    "created_at": pytest.approx(time.time()),
                },
            },
        },
    }


def test_ttl_cache_get() -> None:
    cache = {}
    ttl_cache = TTLCacheAdapter(cache, ("a", "b"))
    key, ttl = "account", 1
    ttl_cache.save(key, 123, ttl=ttl)
    assert ttl_cache[key] == 123

    with pytest.raises(KeyError):
        ttl_cache["invalid_key"]

    assert ttl_cache.get(key) == 123
    time.sleep(ttl + 0.1)
    assert ttl_cache.get(key) is None
    assert cache == {"a": {"b": {}}}
    ttl_cache[key] = "abc"
    assert ttl_cache.get(key) == "abc"
    assert ttl_cache[key] == "abc"
    assert cache == {
        "a": {
            "b": {
                key: {
                    "value": "abc",
                    "ttl": None,
                    "created_at": pytest.approx(time.time()),
                },
            },
        },
    }


def test_invalid_cache(logs: pytest.LogCaptureFixture) -> None:
    cache = {"a": [1, 2, 5]}
    ttl_cache = TTLCacheAdapter(cache, ("a", "b"))

    ttl_cache["key"] = 4
    assert cache == {"a": [1, 2, 5]}
    assert ttl_cache._root == {
        "key": {
            "value": 4,
            "ttl": None,
            "created_at": pytest.approx(time.time()),
        },
    }
    assert logs.messages == ["Invalid cache entry a.b, ignoring"]


async def test_cache_fn() -> None:

    call = 0

    async def update() -> int:
        nonlocal call
        call += 1
        return call

    fn = cached_fn(update)
    assert await fn() == 1
    assert await fn() == 1

    fn = cached_fn(update, ttl=0.2)
    assert await fn() == 1
    assert await fn() == 1

    fn2 = cached_fn(update, key="update2", ttl=0.2)
    assert await fn2() == 2
    assert await fn2() == 2
    await asyncio.sleep(0.2 + 0.1)
    assert await fn2() == 3
    assert _IN_MEMORY_CACHE["test_cache"]["test_cache_fn"]["<locals>"] == {
        "update": {
            "value": 1,
            "ttl": None,
            "created_at": mock.ANY,
        },
        "update2": {
            "value": 3,
            "ttl": 0.2,
            "created_at": mock.ANY,
        },
    }
    fn.clear()
    assert "update" not in _IN_MEMORY_CACHE["test_cache"]["test_cache_fn"]["<locals>"]
    assert await fn() == 4


class Spy:
    def __init__(self, value: object) -> None:
        self.value: object = value
        self.calls: int = 0

    async def __call__(self) -> object:
        self.calls += 1
        return self.value


async def test_cached_fn_concurrent_calls_execute_only_once() -> None:
    spy = Spy("test 2")

    async def factory() -> object:
        await asyncio.sleep(0.02)
        return await spy()

    factory = cached_fn(factory, ttl=60)
    results = await asyncio.gather(*(factory() for _ in range(10)))
    assert len(set(results)) == 1
    assert spy.calls == 1


async def test_cache_returns_same_value_while_not_expired() -> None:
    ttl = 0.5
    spy_ = Spy("test 1")

    def spy():
        return spy_()

    factory = cached_fn(spy, ttl=ttl)
    first = await factory()
    second = await factory()

    assert first == second
    assert spy_.calls == 1
    await asyncio.sleep(ttl + 0.1)
    _ = await factory()
    assert spy_.calls == 2


async def test_ttl_cache_method() -> None:
    cache: dict[str, Any] = {}
    calls = 0

    class A:
        def __init__(self) -> None:
            self.cache: TTLCacheAdapter[Any] = TTLCacheAdapter(cache)

        @disk_cached_method(ttl=0.2)
        async def compute(self) -> int:
            nonlocal calls
            calls += 1
            return calls

    inst = A()
    assert type(inst.compute) is not _DiskCachedMethod
    assert await inst.compute() == 1
    assert await inst.compute() == 1
    inst.compute.clear()
    assert await inst.compute() == 2
    await asyncio.sleep(0.2 + 0.1)
    assert await inst.compute() == 3


@pytest.mark.parametrize(
    ("key", "expected_parent_keys", "expected_key"),
    [
        ("key", [], "key"),
        ("parent.inner", ["parent"], "inner"),
        ("a.b.c", ["a", "b"], "c"),
    ],
)
def test_normalize_key(key: tuple[str, ...], expected_parent_keys: list[str,], expected_key: str) -> None:
    parents, real_key = _normalize_key(key)
    assert parents == expected_parent_keys
    assert real_key == expected_key


def test_ttl_child() -> None:
    cache = {}
    ttl_cache = TTLCacheAdapter(cache, ("a", "b"))
    ttl_cache["c"] = 1

    assert cache == {
        "a": {
            "b": {
                "c": {
                    "value": 1,
                    "ttl": None,
                    "created_at": mock.ANY,
                }
            }
        }
    }
    assert ttl_cache.create_child() is ttl_cache
    inner = ttl_cache.create_child("d")
    inner["f"] = 2
    assert cache == {
        "a": {
            "b": {
                "c": {
                    "value": 1,
                    "ttl": None,
                    "created_at": mock.ANY,
                },
                "d": {
                    "f": {
                        "value": 2,
                        "ttl": None,
                        "created_at": mock.ANY,
                    }
                },
            }
        }
    }
