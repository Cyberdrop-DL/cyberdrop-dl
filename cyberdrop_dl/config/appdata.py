from __future__ import annotations

import dataclasses
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, final

from cyberdrop_dl import env

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)
_win_appdata: Path | None = None
_default_app_dirs: AppDirs | None = None
_appname = "cyberdrop-dl"
_logs_folder = "Logs" if os.name == "nt" else "logs"


def _windows_appdata() -> Path:
    # Detect the real path when running in sandboxed interpreter (ex: UWP Python)
    # https://github.com/Cyberdrop-DL/cyberdrop-dl/issues/1700#issuecomment-4317561031
    # https://learn.microsoft.com/en-us/windows/msix/desktop/flexible-virtualization#default-msix-behavior

    global _win_appdata  # noqa: PLW0603
    if _win_appdata is not None:
        return _win_appdata

    appdata = Path(os.environ["APPDATA"]) / _appname
    appdata.mkdir(parents=True, exist_ok=True)
    anchor = appdata / "cdl.anchor"
    anchor.touch()
    try:
        _win_appdata = anchor.resolve(strict=True).parent
    finally:
        anchor.unlink(missing_ok=True)

    if appdata != _win_appdata:
        logger.warning("Windows virtualized path detected at '%s'. Real destination: '%s'", appdata, _win_appdata)
    try:
        _win_appdata.rmdir()
    except OSError:
        pass
    return _win_appdata


def _resolve(path: Path) -> Path:
    return path.expanduser().resolve().absolute()


def _xdg_expand(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser()


class XDG:
    CACHE_HOME: Path = _xdg_expand("XDG_CACHE_HOME", "~/.cache")
    CONFIG_HOME: Path = _xdg_expand("XDG_CONFIG_HOME", "~/.config")
    DATA_HOME: Path = _xdg_expand("XDG_DATA_HOME", "~/.local/share")
    STATE_HOME: Path = _xdg_expand("XDG_STATE_HOME", "~/.local/state")


@final
@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class AppDirs:
    cache: Path
    config: Path
    data: Path
    logs: Path

    @staticmethod
    def from_path(path: Path) -> AppDirs:
        return AppDirs(
            cache=path,
            config=path,
            data=path,
            logs=path,
        )

    @staticmethod
    def default() -> AppDirs:
        global _default_app_dirs  # noqa: PLW0603
        if _default_app_dirs is not None:
            return _default_app_dirs

        app_dirs = _default_app_dir()
        object.__setattr__(app_dirs, "logs", app_dirs.logs / _logs_folder)
        _default_app_dirs = app_dirs
        return _default_app_dirs

    def __iter__(self) -> Iterator[tuple[str, Path]]:
        for field in dataclasses.fields(self):
            yield field.name, getattr(self, field.name)

    def __json__(self) -> dict[str, str]:
        return {k: str(v) for k, v in self}


def _default_app_dir() -> AppDirs:
    if "pytest" in sys.modules:
        temp_dir = Path(tempfile.TemporaryDirectory(prefix="cdl_", delete=False).name)
        return AppDirs.from_path(temp_dir)

    if env.APPDATA_FOLDER:
        return AppDirs.from_path(_resolve(Path(env.APPDATA_FOLDER)))

    if os.name == "nt":
        return AppDirs.from_path(_windows_appdata())

    return AppDirs(
        cache=_resolve(XDG.CACHE_HOME) / _appname,
        config=_resolve(XDG.CONFIG_HOME) / _appname,
        data=_resolve(XDG.DATA_HOME) / _appname,
        logs=_resolve(XDG.STATE_HOME) / _appname,
    )


@final
@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class AppData:
    config_file: Path
    cache_file: Path
    db_file: Path
    logs_folder: Path

    __iter__ = AppDirs.__iter__
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
        return AppData.from_dirs(AppDirs.default())

    @staticmethod
    def from_dirs(app_dirs: AppDirs) -> AppData:
        return AppData(
            config_file=app_dirs.config / "config.yaml",
            cache_file=app_dirs.cache / "cache.json",
            db_file=app_dirs.data / "cyberdrop.db",
            logs_folder=app_dirs.logs,
        )

    def mkdirs(self) -> None:
        for folder in {
            self.config_file.parent,
            self.cache_file.parent,
            self.db_file.parent,
            self.logs_folder,
        }:
            folder.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    print(AppDirs.default().__json__())  # noqa: T201
