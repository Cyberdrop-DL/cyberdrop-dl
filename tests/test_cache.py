from pathlib import Path
from typing import Any

from cyberdrop_dl import __version__, yaml
from cyberdrop_dl.managers.manager import Manager, _cache_context


def test_cache_file_is_not_saved_outside_ctx() -> None:
    manager = Manager()
    cache_file = manager.appdata.cache_file
    manager.cache["test"] = 1
    assert manager.cache == {"test": 1}
    assert not cache_file.exists()


def test_cache_file_is_saved_in_ctx(tmp_path: Path) -> None:
    cache_file = tmp_path / "cache_file.txt"
    cache: dict[str, Any] = {}
    with _cache_context(cache_file, cache):
        cache["test"] = 1
        assert cache == {"test": 1}
        assert cache_file.is_file()

    assert cache_file.is_file()
    assert yaml.load(cache_file) == {"test": 1, "version": __version__}
