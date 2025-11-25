from __future__ import annotations

import asyncio
import functools
import itertools
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final, NamedTuple

import psutil
from pydantic import ByteSize

from cyberdrop_dl.exceptions import InsufficientFreeSpaceError
from cyberdrop_dl.utils.logger import log, log_debug

if TYPE_CHECKING:
    from collections.abc import Generator

    from psutil._common import sdiskpart

    from cyberdrop_dl.data_structures.url_objects import MediaItem
    from cyberdrop_dl.managers.manager import Manager


@dataclass(frozen=True, slots=True, order=True)
class DiskPartition:
    mountpoint: Path
    device: Path = field(compare=False)
    fstype: str = field(compare=False)
    opts: str = field(compare=False)

    @staticmethod
    def from_psutil(diskpart: sdiskpart) -> DiskPartition:
        # Resolve converts any mapped drive to UNC paths (windows)
        return DiskPartition(
            Path(diskpart.mountpoint).resolve(),
            Path(diskpart.device).resolve(),
            diskpart.fstype,
            diskpart.opts,
        )


class MountStats(NamedTuple):
    partition: DiskPartition
    free_space: ByteSize

    def __str__(self) -> str:
        free_space = self.free_space.human_readable(decimal=True)
        stats_as_dict = asdict(self.partition) | {"free_space": free_space}
        return ", ".join(f"'{k}': '{v}'" for k, v in stats_as_dict.items())


_CHECK_PERIOD: Final = 2  # how often the check_free_space_loop will run (in seconds)
_LOG_PERIOD: Final = 10  # log storage details every <x> loops, AKA log every 20 (2x10) seconds,


class StorageManager:
    """Runs an infinite loop to keep an updated value of the available space on all storage devices."""

    def __init__(self, manager: Manager):
        self.manager: Manager = manager
        self.total_data_written: int = 0
        self._used_mounts: set[Path] = set()
        self._free_space: dict[Path, int] = {}
        self._mount_addition_locks: dict[Path, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._updated: asyncio.Event = asyncio.Event()
        self._partitions = list(_get_disk_partitions())
        self._loop = asyncio.create_task(self._check_free_space_loop())
        self._unavailable_mounts: set[Path] = set()

    @property
    def mounts(self) -> tuple[Path, ...]:
        return tuple(p.mountpoint for p in self._partitions)

    @property
    def _simplified_stats(self) -> str:
        stats_as_str = "\n".join(f"    {mount_stats!s}" for mount_stats in self._mount_stats())
        return f"Storage status:\n {stats_as_str}"

    def _mount_stats(self) -> Generator[MountStats]:
        """Returns information of every used mount + its free space."""

        for partition in self._partitions:
            free_space = self._free_space.get(partition.mountpoint)
            if free_space is not None:
                yield MountStats(partition, ByteSize(free_space))

    async def check_free_space(self, media_item: MediaItem) -> None:
        """Checks if there is enough free space to download this item."""

        await self.manager.states.RUNNING.wait()
        if not await self._has_sufficient_space(media_item.download_folder):
            raise InsufficientFreeSpaceError(origin=media_item)

    async def reset(self) -> None:
        # This is causing lockups
        # await self._updated.wait()  # Make sure a query is not running right now
        self.total_data_written = 0
        self._used_mounts = set()
        self._free_space = {}

    async def close(self) -> None:
        await self.reset()
        try:
            self._loop.cancel()
            await self._loop
        except asyncio.CancelledError:
            pass

    async def _check_nt_network_drive(self, folder: Path) -> None:
        """Checks is the drive of this folder is a Windows network drive (UNC or unknown mapped drive) and exists."""
        # See: https://github.com/jbsparrow/CyberDropDownloader/issues/860
        if not psutil.WINDOWS:
            return

        # We can discard mapped drives because they would have been converted to UNC path at startup
        # calling resolve on a mapped network drive returns its UNC path
        # it would only still be a mapped drive is the network address is not available
        is_mapped_drive = ":" in folder.drive and len(folder.drive) == 2
        is_unc_path = folder.drive.startswith("\\\\")
        if is_mapped_drive or not is_unc_path:
            return

        folder_drive = _drive_as_path(folder.drive)
        async with self._mount_addition_locks[folder_drive]:
            if folder_drive in itertools.chain(self._unavailable_mounts, self.mounts):
                return

            msg = f"Checking new possible network_drive: '{folder_drive}' for folder '{folder}'"
            log_debug(msg)

            try:
                is_dir = await asyncio.to_thread(folder_drive.is_dir)
            except OSError:
                is_dir = False

            if is_dir:
                net_drive = DiskPartition(folder_drive, folder_drive, "network_drive", "")
                self._partitions.append(net_drive)

            else:
                self._unavailable_mounts.add(folder_drive)

    async def _has_sufficient_space(self, folder: Path) -> bool:
        """Checks if there is enough free space to download to this folder.

        `folder` must be an absolute path"""

        await self._check_nt_network_drive(folder)
        mount = _get_mount_point(folder, self.mounts)
        if not mount:
            return False

        async with self._mount_addition_locks[mount]:
            if mount not in self._free_space:
                # Manually query this mount now. Next time it will be part of the loop

                self._free_space[mount] = await self._get_free_space(mount)
                self._used_mounts.add(mount)
                log(f"A new mountpoint ('{mount!s}') will be used for '{folder}'")
                log(self._simplified_stats)

        free_space = self._free_space[mount]
        if free_space == -1:
            return True
        return free_space > self.manager.global_config.general.required_free_space

    async def _get_free_space(self, mount: Path) -> int:
        exc_info = None
        free_space = 0

        try:
            result = await asyncio.to_thread(psutil.disk_usage, str(mount))
            free_space = result.free
        except OSError as e:
            if "operation not supported" in str(e).casefold():
                exc_info = e
            else:
                raise

        if exc_info or (free_space == 0 and self._is_fuse_fs(mount)):
            msg = f"Unable to get free space from mount point ('{mount!s}')'. Skipping free space check"
            log(msg, 40, exc_info=exc_info)
            free_space = -1

        return free_space

    def _get_partition(self, mount: Path) -> DiskPartition | None:
        for partition in self._partitions:
            if mount.is_relative_to(partition.mountpoint):
                return partition

    def _is_fuse_fs(self, mount: Path) -> bool:
        if partition := self._get_partition(mount):
            return "fuse" in partition.fstype
        return False

    async def _check_free_space_loop(self) -> None:
        """Infinite loop to get free space of all used mounts and update internal dict"""

        last_check = -1
        while True:
            await self.manager.states.RUNNING.wait()
            self._updated.clear()
            last_check += 1
            if self._used_mounts:
                used_mounts = sorted(mount for mount in self._used_mounts if self._free_space[mount] != -1)
                tasks = [self._get_free_space(mount) for mount in used_mounts]
                results = await asyncio.gather(*tasks)
                for mount, free_space in zip(used_mounts, results, strict=True):
                    self._free_space[mount] = free_space
                if last_check % _LOG_PERIOD == 0:
                    log_debug(self._simplified_stats)

            self._updated.set()
            await asyncio.sleep(_CHECK_PERIOD)


@functools.lru_cache
def _get_mount_point(folder: Path, all_mounts: tuple[Path, ...]) -> Path | None:
    # Cached for performance.
    # It's not an expensive operation nor IO blocking, but it's very common for multiple files to share the same download folder
    # ex: HLS downloads could have over a thousand segments. All of them will go to the same folder
    assert folder.is_absolute()
    possible_mountpoints = (mount for mount in all_mounts if folder.is_relative_to(mount))

    # Get the closest mountpoint to `folder`
    # mount_a = /home/user/  -> points to an internal SSD
    # mount_b = /home/user/USB -> points to an external USB drive
    # If `folder`` is `/home/user/USB/videos`, the correct mountpoint is mount_b
    if mount_point := max(possible_mountpoints, key=lambda path: len(path.parts), default=None):
        return mount_point

    # Mount point for this path does not exists
    # This will only happen on Windows, ex: an USB drive (`D:`) that is not currently available (AKA disconnected)
    # On Unix there's always at least 1 mountpoint, root (`/`)
    msg = f"No available mountpoint found for '{folder}'"
    msg += f"\n -> drive = '{_drive_as_path(folder.drive)}' , last_parent = '{folder.parents[-1]}'"
    log(msg, 40)


def _drive_as_path(drive: str) -> Path:
    is_mapped_drive = ":" in drive and len(drive) == 2
    return Path(f"{drive}/" if is_mapped_drive else drive)


def _get_disk_partitions() -> Generator[DiskPartition]:
    for p in psutil.disk_partitions(all=True):
        try:
            yield DiskPartition.from_psutil(p)
        except OSError as e:
            msg = f"Unable to get information about {p.mountpoint}. All files with that mountpoint as target will be skipped: {e!r}"
            log(msg, 40)
