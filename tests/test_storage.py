import dataclasses
from collections.abc import AsyncGenerator
from pathlib import Path
from unittest import mock

import pytest

from cyberdrop_dl.managers.manager import Manager
from cyberdrop_dl.managers.storage_manager import StorageManager


@pytest.fixture
async def storage(running_manager: Manager) -> AsyncGenerator[StorageManager]:
    yield StorageManager(running_manager)


async def test_unsupported_fs_should_not_return_zero(storage: StorageManager) -> None:
    cwd = Path().resolve()
    free_space = await storage._get_free_space(cwd)
    assert free_space > 0
    with mock.patch("psutil.disk_usage", side_effect=OSError(None, "operation not supported")):
        free_space = await storage._get_free_space(cwd)
        assert free_space == -1

    with mock.patch("psutil.disk_usage", side_effect=OSError(None, "another error")):
        with pytest.raises(OSError):
            await storage._get_free_space(cwd)


async def test_fuse_filesystem_should_not_return_zero(storage: StorageManager) -> None:
    cwd = Path().resolve()
    partition = storage._get_partition(cwd)
    assert partition
    storage._partitions = [dataclasses.replace(partition, fstype="fuse")]

    free_space = await storage._get_free_space(cwd)
    assert free_space > 0

    class NullUsage:
        free = 0

    with mock.patch("psutil.disk_usage", return_value=NullUsage()):
        free_space = await storage._get_free_space(cwd)
        assert free_space == -1
