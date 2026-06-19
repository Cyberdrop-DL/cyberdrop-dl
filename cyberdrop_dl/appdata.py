from __future__ import annotations

import dataclasses
import logging
import os
from enum import StrEnum
from pathlib import Path
from typing import final

_WIN_APPDATA: Path | None = None
logger = logging.getLogger(__name__)
_appname = "cyberdrop-dl"


def _windows_appdata() -> Path:
    # Detect the real path when running in sandboxed interpreter (ex: UWP Python)
    # https://github.com/Cyberdrop-DL/cyberdrop-dl/issues/1700#issuecomment-4317561031
    # https://learn.microsoft.com/en-us/windows/msix/desktop/flexible-virtualization#default-msix-behavior

    global _WIN_APPDATA  # noqa: PLW0603
    if _WIN_APPDATA is not None:
        return _WIN_APPDATA
    appdata = _expand("%APPDATA%") / _appname
    appdata.mkdir(parents=True, exist_ok=True)
    anchor = appdata / "cdl.anchor"
    anchor.touch()
    try:
        real_appdata = _WIN_APPDATA = anchor.resolve().parent  # pyright: ignore[reportConstantRedefinition]
        if appdata != real_appdata:
            logger.warning("Windows virtualized path detected at '%s'. Real destination: '%s'", appdata, real_appdata)
        try:
            real_appdata.rmdir()
        except OSError:
            pass
        return real_appdata
    finally:
        anchor.unlink()


def _expand(path: os.PathLike[str] | str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path)))  # noqa: PTH111


def _resolve(path: os.PathLike[str] | str) -> Path:
    return Path(path).resolve().absolute()


class XDG:
    CACHE_HOME: Path = _expand(os.getenv("XDG_CACHE_HOME") or "~/.cache")
    CONFIG_HOME: Path = _expand(os.getenv("XDG_CONFIG_HOME") or "~/.config")
    DATA_HOME: Path = _expand(os.getenv("XDG_DATA_HOME") or "~/.local/share")
    STATE_HOME: Path = _expand(os.getenv("XDG_STATE_HOME") or "~/.local/state")


class AppFiles(StrEnum):
    cache = "cache.json"
    config = "config.yaml"
    database = "cyberdrop.db"


@final
@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class AppDirs:
    cache: Path
    config: Path
    data: Path
    logs: Path

    @staticmethod
    def default() -> AppDirs:
        if os.name == "nt":
            appdata = _windows_appdata()
            return AppDirs(
                cache=appdata,
                config=appdata,
                data=appdata,
                logs=appdata / "Logs",
            )

        return AppDirs(
            cache=_resolve(XDG.CACHE_HOME) / _appname,
            config=_resolve(XDG.CONFIG_HOME) / _appname,
            data=_resolve(XDG.DATA_HOME) / _appname,
            logs=_resolve(XDG.STATE_HOME) / _appname / "logs",
        )

    def __json__(self) -> dict[str, str]:
        return {k: str(v) for k, v in dataclasses.asdict(self).items()}


@final
@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class AppData:
    config_file: Path
    cache_file: Path
    db_file: Path
    logs_folder: Path

    __json__ = AppDirs.__json__

    @staticmethod
    def default() -> AppData:
        app_dirs = AppDirs.default()
        return AppData(
            config_file=app_dirs.config / AppFiles.config,
            cache_file=app_dirs.cache / AppFiles.cache,
            db_file=app_dirs.data / AppFiles.database,
            logs_folder=app_dirs.logs,
        )


if __name__ == "__main__":
    print(AppDirs.default().__json__())  # noqa: T201
