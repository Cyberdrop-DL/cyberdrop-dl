from pathlib import Path

import pytest

from cyberdrop_dl.crawlers.crawler import _check_path_traversal
from cyberdrop_dl.exceptions import PathTraversalError


def test_path_inside_dl_folder_are_ok(tmp_path: Path) -> None:
    dl = tmp_path / "downloads"
    sub = dl / "a" / "b"
    sub.mkdir(parents=True)

    _check_path_traversal(dl, sub)
    _check_path_traversal(dl, dl / "a/b")


def test_dot_files_raise_exception(tmp_path: Path) -> None:
    dl = tmp_path / "downloads"
    dl.mkdir()

    with pytest.raises(PathTraversalError):
        _check_path_traversal(dl, Path("a/./b"))

    with pytest.raises(PathTraversalError):
        _check_path_traversal(dl, Path("a/../b"))


def test_symlinks_outside_dl_path_raise_error(tmp_path: Path) -> None:
    """A symlink that points outside the download folder must be rejected."""
    dl = tmp_path / "downloads"
    dl.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    symlink = dl / "evil"
    symlink.symlink_to(outside)

    with pytest.raises(PathTraversalError):
        _check_path_traversal(dl, symlink)


def test_traversal_paths_should_raise_error(tmp_path: Path) -> None:
    """A path like '../../etc' must be rejected."""
    dl = tmp_path / "downloads"
    dl.mkdir()

    with pytest.raises(PathTraversalError):
        _check_path_traversal(dl, Path(".."))

    with pytest.raises(PathTraversalError):
        _check_path_traversal(dl, dl / ".." / "etc")
