from __future__ import annotations

import dataclasses
import os
from pathlib import Path
from unittest import mock

import pytest

from cyberdrop_dl import storage
from cyberdrop_dl.storage import _psutil


def create_partition(path: str):
    return _psutil.DiskPartition(Path(path), Path(path), "", "")


def find_partition(path: str):
    return _psutil._find_partition(Path(path))


async def test_unsupported_fs_should_not_return_zero(tmp_path: Path) -> None:
    free_space = _psutil._disk_usage(tmp_path)
    assert free_space > 0
    with mock.patch("psutil.disk_usage", side_effect=OSError(None, "operation not supported")):
        free_space = _psutil._disk_usage(tmp_path)
        assert free_space == -1

    with mock.patch("psutil.disk_usage", side_effect=OSError(None, "another error")):
        with pytest.raises(OSError):
            _ = _psutil._disk_usage(tmp_path)


def test_fuse_filesystem_should_not_return_zero(tmp_path: Path) -> None:
    partition = _psutil._find_partition(tmp_path)
    assert partition
    assert not _psutil._is_fuse_fs(tmp_path)
    _psutil._PARTITIONS = [dataclasses.replace(partition, fstype="fuse")]  # pyright: ignore[reportPrivateUsage]
    assert _psutil._is_fuse_fs(tmp_path)

    free_space = _psutil._disk_usage(tmp_path)
    assert free_space > 0

    class NullUsage:
        free = 0

    with mock.patch("psutil.disk_usage", return_value=NullUsage()):
        free_space = _psutil._disk_usage(tmp_path)
        assert free_space == -1


def test_storage_only_work_with_abs_paths() -> None:
    cwd = Path()
    with pytest.raises(ValueError):
        _ = _psutil._find_partition(cwd)

    assert _psutil._find_partition(cwd.resolve())


@pytest.mark.skipif(os.name == "nt", reason="Test paths are only posix")
def test_find_partition_finds_the_correct_partition() -> None:

    root, home, usb, external_ssd = partitions = [
        create_partition(path) for path in ("/", "/home", "/mnt/USB", "/home/external_SSD")
    ]

    _psutil._PARTITIONS = partitions  # pyright: ignore[reportPrivateUsage]

    assert find_partition("/swap_file") is root
    assert find_partition("/home/user/.bash_rc") is home
    assert find_partition("/home/external_SSD/song.mp3") is external_ssd
    assert find_partition("/mnt/USB") is usb
    assert find_partition("/mnt") is root


@pytest.mark.skipif(os.name != "nt", reason="Test paths are only for windows")
def test_find_partition_finds_the_correct_partition_windows() -> None:
    c_drive, d_drive = partitions = [create_partition(path) for path in ("C:/", "D:/")]

    _psutil._PARTITIONS = partitions  # pyright: ignore[reportPrivateUsage]

    assert find_partition("C:/pagefile") is c_drive
    assert find_partition("C:/") is c_drive
    assert find_partition("D:/music/song.mp3") is d_drive
    assert find_partition("Z:/") is None


async def test_no_psutil_check_does_not_raise_exception(tmp_path: Path) -> None:
    with mock.patch.object(storage, "_psutil_loop", None):
        async with storage.monitor(100):
            assert await storage.has_sufficient_space(tmp_path)


def test_no_psutil_returns_size_of_closest_parent_on_file_that_does_not_exists(tmp_path: Path) -> None:
    folder = tmp_path / "folder_abc/that/does/not/exists"
    result = storage._disk_usage(folder)
    assert result > 1e10
    assert result == pytest.approx(storage._disk_usage(tmp_path), abs=1e6)


async def test_psutil_returns_size_of_closest_parent_on_file_that_does_not_exists(tmp_path: Path) -> None:
    folder = tmp_path / "folder_abc/that/does/not/exists"
    result = await _psutil.get_free_space(folder)
    assert result > 1e10
    assert result == pytest.approx(await _psutil.get_free_space(tmp_path), abs=1e6)


async def test_psutil_raw_raises_file_not_found_error_on_file_that_does_not_exists(tmp_path: Path) -> None:
    folder = tmp_path / "folder_abc/that/does/not/exists"
    with pytest.raises(FileNotFoundError):
        _ = _psutil._disk_usage(folder)
