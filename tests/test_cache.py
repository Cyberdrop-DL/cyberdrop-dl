from pathlib import Path
from typing import Any

from cyberdrop_dl import __version__
from cyberdrop_dl.config.appdata import AppData
from cyberdrop_dl.manager import Manager, _cache_context
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
    with _cache_context(cache_file, cache):
        cache["test"] = 1
        assert cache == {"test": 1}
        assert cache_file.is_file()

    assert cache_file.is_file()
    assert json.loads(cache_file.read_text()) == {"test": 1, "version": __version__}
