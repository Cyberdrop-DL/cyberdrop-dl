from __future__ import annotations

import dataclasses
import logging
import os
from enum import StrEnum
from pathlib import Path
from typing import final

logger = logging.getLogger(__name__)
_win_appdata: Path | None = None
_default_app_dirs: AppDirs | None = None
_appname = "cyberdrop-dl"


def _windows_appdata() -> Path:
    # Detect the real path when running in sandboxed interpreter (ex: UWP Python)
    # https://github.com/Cyberdrop-DL/cyberdrop-dl/issues/1700#issuecomment-4317561031
    # https://learn.microsoft.com/en-us/windows/msix/desktop/flexible-virtualization#default-msix-behavior

    global _win_appdata  # noqa: PLW0603
    if _win_appdata is not None:
        return _win_appdata
    appdata = _expand("%APPDATA%") / _appname
    appdata.mkdir(parents=True, exist_ok=True)
    anchor = appdata / "cdl.anchor"
    anchor.touch()
    try:
        real_appdata = _win_appdata = anchor.resolve().parent  # pyright: ignore[reportConstantRedefinition]
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
    return Path(os.path.expandvars(path)).expanduser()


def _resolve(path: os.PathLike[str] | str) -> Path:
    return Path(path).expanduser().resolve().absolute()


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
        global _default_app_dirs  # noqa: PLW0603
        if _default_app_dirs is not None:
            return _default_app_dirs

        if os.name == "nt":
            appdata = _windows_appdata()
            _default_app_dirs = AppDirs(
                cache=appdata,
                config=appdata,
                data=appdata,
                logs=appdata / "Logs",
            )

        else:
            _default_app_dirs = AppDirs(
                cache=_resolve(XDG.CACHE_HOME) / _appname,
                config=_resolve(XDG.CONFIG_HOME) / _appname,
                data=_resolve(XDG.DATA_HOME) / _appname,
                logs=_resolve(XDG.STATE_HOME) / _appname / "logs",
            )
        return _default_app_dirs

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
    def create(
        *,
        config_file: Path | None = None,
        cache_file: Path | None = None,
        db_file: Path | None = None,
    ):
        default = AppData.default()

        def resolve(path: Path | None) -> Path | None:
            return _resolve(path) if path else None

        return AppData(
            config_file=resolve(config_file) or default.config_file,
            cache_file=resolve(cache_file) or default.cache_file,
            db_file=resolve(db_file) or default.db_file,
            logs_folder=default.logs_folder,
        )

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
