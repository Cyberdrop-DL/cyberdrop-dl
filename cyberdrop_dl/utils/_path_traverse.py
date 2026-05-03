import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _safe_get_size(path: os.DirEntry[str]) -> int | None:
    try:
        return path.stat(follow_symlinks=False).st_size
    except (OSError, ValueError):
        return


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


def delete_empty_files_and_folders_in_place(dirname: Path | str) -> bool:
    """Recursively delete empty files and directories from *dirname*.

    Every empty file is removed immediately, and a directory is removed only when all of its children have already been
    walked and the dir itself is also empty"""

    has_non_empty_files = False
    has_non_empty_subfolders = False

    try:
        for entry in os.scandir(dirname):
            if _safe_is_dir(entry):
                deleted = delete_empty_files_and_folders_in_place(entry.path)
                if not deleted:
                    has_non_empty_subfolders = True
            elif _safe_get_size(entry) == 0:
                deleted = _safe_delete(entry)
                if not deleted:
                    has_non_empty_files = True
            else:
                has_non_empty_files = True

    except OSError as e:
        logger.error(f"Unexpected error while walking '{dirname}' ({e!r})")
        return False

    if has_non_empty_files or has_non_empty_subfolders:
        return False
    try:
        os.rmdir(dirname)  # noqa: PTH106
        return True
    except OSError:
        return False
