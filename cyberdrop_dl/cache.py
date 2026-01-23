from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cyberdrop_dl import __version__ as current_version
from cyberdrop_dl.utils import yaml

if TYPE_CHECKING:
    from pathlib import Path


class Cache:
    def __init__(self, cache_file: Path) -> None:
        self.cache_file = cache_file
        self._cache: dict[str, Any] = {}
        if not self.cache_file.is_file():
            self.save("default_config", "Default")
        else:
            self._cache = yaml.load(self.cache_file)

    def get(self, key: str) -> Any:
        """Returns the value of a key in the cache."""
        return self._cache.get(key, None)

    def save(self, key: str, value: Any) -> None:
        """Saves a key and value to the cache."""
        self._cache[key] = value
        yaml.save(self.cache_file, self._cache)

    async def close(self) -> None:
        self.save("version", current_version)
