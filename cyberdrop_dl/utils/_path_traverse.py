from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from cyberdrop_dl.constants import TempExt

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

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


def _safe_delete(entry: os.DirEntry[str]) -> bool:
    try:
        os.unlink(entry)  # noqa: PTH108
    except OSError as e:
        logger.error(f"Unable to delete '{entry.path}' ({e!r})")
        return False
    else:
        logger.debug(f"Deleted '{entry.path}'")
        return True


def _safe_rmdir(dirname: Path | str) -> bool:
    try:
        os.rmdir(dirname)  # noqa: PTH106
    except OSError:
        return False
    else:
        return True


def partial_files(path: Path | str, /) -> Generator[Path]:
    try:
        for entry in os.scandir(path):
            if _safe_is_dir(entry):
                yield from partial_files(entry.path)
                continue

            suffix = entry.name.rpartition(".")[-1]
            if f".{suffix}" in TempExt:
                yield Path(entry.path)
    except OSError:
        return


def has_partial_files(path: Path) -> bool:
    return bool(next(partial_files(path), False))


def delete_empty_files_and_folders_in_place(
    dirname: Path | str, *, exclude: Iterable[Path | None] | None = None
) -> bool:
    """Recursively delete empty files and directories from *dirname*.

    Every empty file is removed immediately, and a directory is removed only when all of its children have already been
    walked and the dir itself is also empty"""
    to_exclude: set[str] = set() if exclude is None else set(map(str, filter(None, exclude)))
    return _delete_empty_files_and_folders_in_place(dirname, to_exclude)


def _delete_empty_files_and_folders_in_place(dirname: Path | str, exclude: set[str]) -> bool:
    has_on_empty_children = False

    try:
        for entry in os.scandir(dirname):
            if entry.name.startswith(".") or entry.path in exclude:
                has_on_empty_children = True
                continue

            if _safe_is_dir(entry):
                deleted = _delete_empty_files_and_folders_in_place(entry.path, exclude)
                if not deleted:
                    has_on_empty_children = True
            elif _safe_get_size(entry) == 0:
                deleted = _safe_delete(entry)
                if not deleted:
                    has_on_empty_children = True
            else:
                has_on_empty_children = True

    except OSError as e:
        logger.error(f"Unexpected error while walking '{dirname}' ({e!r})")
        return False

    return (not has_on_empty_children) and _safe_rmdir(dirname)
