from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from cyberdrop_dl import context
from cyberdrop_dl.constants import TempExt

if TYPE_CHECKING:
    from collections.abc import Container, Generator

logger = logging.getLogger(__name__)


def _safe_get_size(path: os.DirEntry[str]) -> int | None:
    try:
        return path.stat(follow_symlinks=False).st_size
    except (OSError, ValueError):
        return None


def _safe_is_dir(entry: os.DirEntry[str]) -> bool:
    try:
        return entry.is_dir(follow_symlinks=False)
    except OSError:
        return False


def _safe_delete_empty(entry: os.DirEntry[str]) -> bool:
    try:
        os.unlink(entry)  # noqa: PTH108
    except OSError as e:
        logger.error(f"Unable to delete '{entry.path}' ({e!r})")
        return False
    else:
        logger.debug(f"Deleted '{entry.path}' (empty file)")
        return True


def _safe_rmdir(dirname: Path | str) -> bool:
    try:
        os.rmdir(dirname)  # noqa: PTH106
    except OSError:
        return False
    else:
        return True


def _partial_files(path: Path | str, /) -> Generator[Path]:
    try:
        for entry in os.scandir(path):
            if _safe_is_dir(entry):
                yield from _partial_files(entry.path)
                continue

            suffix = entry.name.rpartition(".")[-1]
            if f".{suffix}" in TempExt:
                yield Path(entry.path)
    except OSError:
        return


def has_partial_files(path: Path) -> bool:
    return bool(next(_partial_files(path), False))


def rm_partial_files(path: Path) -> None:
    for file in _partial_files(path):
        try:
            file.unlink()
        except OSError as e:
            logger.error(f"Unable to delete '{file}' ({e!r})")
        else:
            logger.debug(f"Deleted '{file}'")


def rm_empty_dirs(path: Path) -> None:
    """Recursively delete empty files and directories in <path>.

    Every empty file is removed immediately. Dirs are removed only if all of its children have already been
    walked and the dir itself is also empty"""
    if not path.is_dir():
        return

    exclude: set[str] = {str(log_file)} if (log_file := context.MAIN_LOG_FILE.get(None)) else set()
    _ = _rm_empty_dirs(path, exclude=exclude)


def _should_ignore(entry: os.DirEntry[str]) -> bool:
    if entry.name.startswith("."):
        return True
    stem, _, ext = entry.name.rpartition(".")
    if not stem:
        return False
    suffix = f".{ext.casefold()}"
    return suffix in {".py", ".anchor"}


def _rm_empty_dirs(dirname: Path | str, exclude: Container[str] = ()) -> bool:
    is_empty = True

    try:
        for entry in os.scandir(dirname):
            if _should_ignore(entry) or entry.path in exclude:
                is_empty = False
                continue

            if _safe_is_dir(entry):
                deleted = _rm_empty_dirs(entry.path, exclude)
                if not deleted:
                    is_empty = False
            elif _safe_get_size(entry) == 0:
                deleted = _safe_delete_empty(entry)
                if not deleted:
                    is_empty = False
            else:
                is_empty = False

    except OSError as e:
        logger.error(f"Unexpected error while walking '{dirname}' ({e!r})")
        return False

    return is_empty and _safe_rmdir(dirname)
