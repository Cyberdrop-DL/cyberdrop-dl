from __future__ import annotations

from typing import TYPE_CHECKING

from cyberdrop_dl.utils import delete_empty_files_and_folders
from cyberdrop_dl.utils._path_traverse import delete_empty_files_and_folders_in_place

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def make_file(root: Path, *parts: str, size: int = 0) -> Path:
    path = root.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


def test_empty_root_is_removed(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    assert delete_empty_files_and_folders_in_place(root) is True
    assert not root.exists()


def test_non_empty_root_is_preserved(tmp_path: Path) -> None:
    root = tmp_path / "data"
    make_file(root, "keep.txt", size=1)
    assert delete_empty_files_and_folders_in_place(root) is False
    assert root.exists()


def test_empty_files_are_deleted(tmp_path: Path) -> None:
    root = tmp_path / "mixed"
    make_file(root, "empty1.txt")
    make_file(root, "empty2.log")
    file = make_file(root, "full.bin", size=10)

    assert delete_empty_files_and_folders_in_place(root) is False
    assert root.exists()
    assert list(root.rglob("*")) == [file]


def test_nested_empty_dirs_are_removed(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    (root / "a" / "b" / "c").mkdir(exist_ok=True, parents=True)
    assert delete_empty_files_and_folders_in_place(root) is True
    assert not root.exists()


def test_nested_with_content_preserved(tmp_path: Path) -> None:
    root = tmp_path / "tree"
    make_file(root, "a", "b", "keep.txt", size=1)
    (root / "empty" / "b" / "c").mkdir(exist_ok=True, parents=True)
    assert delete_empty_files_and_folders_in_place(root) is False
    assert root.exists()
    assert (root / "a" / "b" / "keep.txt").exists()
    assert not (root / "empty").exists()


def test_unreadable_directory_returns_false(tmp_path: Path) -> None:
    root = tmp_path / "protected"
    sub = root / "empty"
    sub.mkdir(exist_ok=True, parents=True)
    sub.chmod(0o000)  # Remove read permission
    try:
        assert delete_empty_files_and_folders_in_place(root) is False
    finally:
        sub.chmod(0o755)


def test_deleted_folder_should_not_emit_any_errors(tmp_path: Path, logs: pytest.LogCaptureFixture) -> None:
    fake_folder = tmp_path / "a_new_folder"
    assert delete_empty_files_and_folders_in_place(fake_folder) is False
    assert "NotFound" in logs.messages[-1]
    logs.clear()
    delete_empty_files_and_folders(fake_folder)
    assert len(logs.messages) == 0
