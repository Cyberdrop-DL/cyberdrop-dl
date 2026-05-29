from pathlib import Path

import pytest

from cyberdrop_dl.exceptions import FileNameError, PathTraversalError
from cyberdrop_dl.utils.filepath import check_dangerous_filename, check_path_traversal


def test_path_inside_dl_folder_are_ok(tmp_path: Path) -> None:
    dl = tmp_path / "downloads"
    sub = dl / "a" / "b"
    sub.mkdir(parents=True)

    check_path_traversal(dl, sub)
    check_path_traversal(dl, dl / "a/b")


def test_path_travesal_attempts_raise_exception(tmp_path: Path) -> None:
    dl = tmp_path / "downloads"
    dl.mkdir()

    with pytest.raises(PathTraversalError):
        check_path_traversal(dl, Path("a/./b"))

    with pytest.raises(PathTraversalError):
        check_path_traversal(dl, Path("a/../b"))


def test_symlinks_outside_dl_path_raises_error(tmp_path: Path) -> None:
    """A symlink that points outside the download folder must be rejected."""
    dl = tmp_path / "downloads"
    dl.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    symlink = dl / "evil"
    symlink.symlink_to(outside)

    with pytest.raises(PathTraversalError):
        check_path_traversal(dl, symlink)


def test_traversal_paths_should_raise_error(tmp_path: Path) -> None:
    """A path like '../../etc' must be rejected."""
    dl = tmp_path / "downloads"
    dl.mkdir()

    with pytest.raises(PathTraversalError):
        check_path_traversal(dl, Path(".."))

    with pytest.raises(PathTraversalError):
        check_path_traversal(dl, dl / ".." / "etc")


@pytest.mark.parametrize(
    "filename",
    [
        ".hidden",
        ".env",
        ".gitignore",
        "....double_dots",
    ],
)
def test_dot_files_are_rejected(filename: str) -> None:
    with pytest.raises(FileNameError) as exc:
        check_dangerous_filename(filename)
    assert exc.value.ui_failure == "Dot file"
    assert filename in str(exc.value)


@pytest.mark.parametrize(
    "filename",
    [
        "report.txt",
        "archive.tar.gz",
        "script.py",
        "README",
        "video.mp4",
    ],
)
def test_known_exceptions_are_accepted(filename: str) -> None:
    check_dangerous_filename(filename)


@pytest.mark.parametrize(
    "filename",
    [
        "malware.exe",
        "payload.EXE",
        "startup.bat",
        "deploy.SH",
        "run.jar",
    ],
)
def test_dangerous_extensions_are_rejected(filename: str) -> None:
    with pytest.raises(FileNameError) as exc:
        check_dangerous_filename(filename)
    assert exc.value.ui_failure == "Dangerous File Extension"
    assert exc.value.message == filename


@pytest.mark.parametrize(
    "filename",
    [
        "f/video.mp4",
        r"f\\payload.mp4",
    ],
)
def test_filenames_w_separators_are_rejected(filename: str) -> None:
    with pytest.raises(FileNameError):
        check_dangerous_filename(filename)
