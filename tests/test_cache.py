import time
from pathlib import Path
from typing import Any

import pytest

from cyberdrop_dl import __version__
from cyberdrop_dl.cache import TTLCacheAdapter, cache_context
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
    assert ttl_cache.create_lookup_path("account") == "a.b.account"
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
    assert ttl_cache.root == {
        "key": {
            "value": 4,
            "ttl": None,
            "created_at": pytest.approx(time.time()),
        },
    }
    assert logs.messages == ["Invalid cache entry a.b, ignoring"]
