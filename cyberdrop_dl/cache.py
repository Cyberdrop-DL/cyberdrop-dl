from __future__ import annotations

import contextlib
import dataclasses
import json
import logging
import time
from typing import TYPE_CHECKING, Any, TypedDict

from cyberdrop_dl import __version__

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

logger = logging.getLogger(__name__)


class _CachedValue[T](TypedDict):
    value: T
    ttl: float | None
    created_at: float


def _has_expired(self: _CachedValue[Any]) -> bool:
    if self["ttl"] is None:
        return False
    return time.time() - self["created_at"] >= self["ttl"]


@dataclasses.dataclass(slots=True)
class TTLCacheAdapter[T]:
    _cache: dict[str, Any]
    _keys: tuple[str, ...] = ()
    _root: dict[str, _CachedValue[Any]] = dataclasses.field(init=False)

    def create_lookup_path(self, *keys: str) -> str:
        return ".".join([*self._keys, *keys])

    @property
    def root(self) -> dict[str, _CachedValue[Any]]:
        try:
            return self._root
        except AttributeError:
            root = self._cache
            for key in self._keys:
                try:
                    root = root.setdefault(key, {})
                except (KeyError, TypeError, ValueError, AttributeError):
                    logger.exception(f"Invalid cache entry {self.create_lookup_path()}, ignoring")
                    root = {}
                    break

            self._root = root
            return self._root

    def __getitem__(self, key: str, /) -> T:
        cache_hit = self._get(key)
        if cache_hit is None:
            raise KeyError(key)
        return cache_hit["value"]

    def _get(self, key: str) -> _CachedValue[T] | None:
        try:
            cache_hit = self.root[key]
        except KeyError:
            return None

        try:
            expired = _has_expired(cache_hit)
        except (KeyError, TypeError, ValueError, AttributeError):
            logger.exception(f"Invalid cache entry {self.create_lookup_path(key)}, ignoring")
            expired = True

        if expired:
            del self[key]
            return None
        return cache_hit

    def __delitem__(self, key: str) -> None:
        del self.root[key]

    def get(self, key: str) -> T | None:
        cache_hit = self._get(key)
        return None if cache_hit is None else cache_hit["value"]

    def save(self, key: str, value: T, *, ttl: float | None = None) -> None:
        """NOTE: cached values MUST be JSON serializable"""
        self.root[key] = {
            "value": value,
            "ttl": ttl,
            "created_at": time.time(),
        }

    def __setitem__(self, name: str, value: T) -> None:
        """NOTE: cached values MUST be JSON serializable"""
        self.save(name, value, ttl=None)


@contextlib.contextmanager
def cache_context(cache_file: Path, cache: dict[str, Any]) -> Generator[None]:
    try:
        content = cache_file.read_text()
    except FileNotFoundError:
        cache_file.parent.mkdir(exist_ok=True, parents=True)
        cache_file.touch()
    else:
        data = json.loads(content)
        assert type(data) is dict
        cache.update(data)
    try:
        yield
    finally:
        cache["version"] = __version__
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True))
