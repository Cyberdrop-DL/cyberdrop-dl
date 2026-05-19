from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

_appname = "cyberdrop_dl"


def _get(envar: str, default: str = "") -> Path:
    path = os.getenv(envar) or default
    assert path
    return Path(path).expanduser()


class XDG:
    CACHE_HOME = _get("XDG_CACHE_HOME", "~/.cache")
    CONFIG_HOME = _get("XDG_CONFIG_HOME", "~/.config")
    DATA_HOME = _get("XDG_DATA_HOME", "~/.local/share")
    STATE_HOME = _get("XDG_STATE_HOME", "~/.local/state")


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class AppData:
    cache: Path
    config: Path
    data: Path
    logs: Path

    def __iter__(self) -> Iterator[Path]:
        return iter(dataclasses.astuple(self))

    def __json__(self) -> dict[str, str]:
        return {name: str(value) for name, value in dataclasses.asdict(self).items()}

    @property
    def database(self) -> Path:
        return self.data / "cyberdrop_dl.db"

    @property
    def config_file(self) -> Path:
        return self.config / "config.toml"

    @property
    def cache_file(self) -> Path:
        return self.cache / "cache.json"


def _default() -> AppData:
    if os.name == "nt":
        WIN_APPDATA = _get("APPDATA", "~/AppData/Roaming")
        return AppData(
            cache=WIN_APPDATA / _appname / "Cache",
            config=WIN_APPDATA / _appname,
            data=WIN_APPDATA / _appname,
            logs=WIN_APPDATA / _appname / "Logs",
        )

    return AppData(
        cache=XDG.CACHE_HOME / _appname,
        config=XDG.CONFIG_HOME / _appname,
        data=XDG.DATA_HOME / _appname,
        logs=XDG.STATE_HOME / _appname / "logs",
    )


DEFAULT = _default()


if __name__ == "__main__":
    import rich

    rich.print(DEFAULT.__json__())
