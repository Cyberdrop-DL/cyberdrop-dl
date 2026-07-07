"""Runs an infinite loop to keep an updated value of the available space on all storage devices."""

from __future__ import annotations

import asyncio
import dataclasses
import functools
import logging
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Final

import psutil

from cyberdrop_dl.models.validators import bytesize_to_str

if TYPE_CHECKING:
    from collections.abc import Generator


logger = logging.getLogger(__name__)
_PARTITIONS: list[DiskPartition] = []
_UNAVAILABLE: set[Path] = set()
_LOCKS: dict[Path, asyncio.Lock] = defaultdict(asyncio.Lock)
_CHECK_PERIOD: Final = 2  # how often the check_free_space_loop will run (in seconds)
_LOG_PERIOD: Final = 60  # log storage details every <x> loops
_free_space: dict[Path, int] = {}


@dataclasses.dataclass(frozen=True, slots=True, order=True)
class DiskPartition:
    mountpoint: Path
    device: Path = dataclasses.field(compare=False)
    fstype: str = dataclasses.field(compare=False)
    opts: str = dataclasses.field(compare=False)

    def __json__(self) -> dict[str, str]:
        return {k: str(v) for k, v in dataclasses.asdict(self).items()}


class _Stats:
    def __json__(self) -> tuple[dict[str, str], ...]:
        return tuple(_partition_stats())

    def __str__(self) -> str:
        return str(self.__json__())


def _disk_usage(path: Path) -> int:
    unsupported = None
    free_space = 0

    try:
        free_space = psutil.disk_usage(str(path)).free
    except OSError as e:
        if "operation not supported" not in str(e).casefold():
            raise

        unsupported = e

    if unsupported or (free_space == 0 and _is_fuse_fs(path)):
        logger.error(
            f"Unable to get free space from mount point ('{path}')'. Skipping free space check",
            exc_info=unsupported,
        )
        return -1

    return free_space


async def get_free_space(folder: Path) -> int:
    await _check_nt_network_drive(folder)
    mount = _get_mount_point(folder)
    if not mount:
        return 0

    free_space = _free_space.get(mount)
    if free_space is None:
        async with _LOCKS[mount]:
            free_space = _free_space.get(mount)
            if free_space is None:
                # Manually query this mount now. Next time it will be part of the loop

                free_space = _free_space[mount] = await asyncio.to_thread(_disk_usage, mount)
                logger.info(f"A new mountpoint ('{mount!s}') will be used for '{folder}'")
                logger.info("Storage status \n%s", _Stats())

    return free_space


def _find_partition(path: Path) -> DiskPartition | None:
    if not path.is_absolute():
        raise ValueError(f"{path!r} is not absolute")

    possible_partitions = (p for p in _partitions() if path.is_relative_to(p.mountpoint))

    # Get the closest mountpoint to `folder`
    # mount_a = /home/user/  -> points to an internal SSD
    # mount_b = /home/user/USB -> points to an external USB drive
    # If `folder`` is `/home/user/USB/videos`, the correct mountpoint is mount_b
    if partition := max(possible_partitions, key=lambda p: len(p.mountpoint.parts), default=None):
        return partition


def _is_fuse_fs(path: Path) -> bool:
    if partition := _find_partition(path):
        return "fuse" in partition.fstype
    return False


def _partitions() -> tuple[DiskPartition, ...]:
    if not _PARTITIONS:
        _PARTITIONS.extend(_get_disk_partitions())
    return tuple(_PARTITIONS)


def _partition_stats() -> Generator[dict[str, str]]:
    for partition in _partitions():
        free_space = _free_space.get(partition.mountpoint)
        if free_space is not None:
            stats = partition.__json__()
            stats["free_space"] = bytesize_to_str(free_space)
            yield stats


def clear_cache() -> None:
    _PARTITIONS.clear()
    _UNAVAILABLE.clear()
    _LOCKS.clear()
    _free_space.clear()
    _get_mount_point.cache_clear()


async def start_loop() -> None:
    """Infinite loop to get free space of all used mounts and update internal dict"""

    async def update() -> None:
        mountpoints = sorted(mount for mount, free_space in _free_space.items() if free_space != -1)
        if not mountpoints:
            return

        usage = await asyncio.gather(*(asyncio.to_thread(_disk_usage, mount) for mount in mountpoints))  # noqa: TID251
        _free_space.update(zip(mountpoints, usage, strict=True))

    last_check = -1
    while True:
        if _free_space:
            last_check += 1
            await update()

            if last_check % _LOG_PERIOD == 0:
                logger.debug("Storage status \n%s", _Stats())

        await asyncio.sleep(_CHECK_PERIOD)


@functools.lru_cache
def _get_mount_point(folder: Path) -> Path | None:
    # Cached for performance.
    # It's not an expensive operation nor IO blocking, but it's very common for multiple files to share the same download folder
    # ex: HLS downloads could have over a thousand segments. All of them will go to the same folder
    if partition := _find_partition(folder):
        return partition.mountpoint

    # Mount point for this path does not exists
    # This will only happen on Windows, ex: an USB drive (`D:`) that is not currently available (AKA disconnected)
    # On Unix there's always at least 1 mountpoint, root (`/`)
    msg = f"No available mountpoint found for '{folder}'"
    msg += f"\n -> drive = '{_drive_as_path(folder.drive)}' , last_parent = '{folder.parents[-1]}'"
    logger.error(msg)


def _drive_as_path(drive: str) -> Path:
    is_mapped_drive = ":" in drive and len(drive) == 2
    return Path(f"{drive}/" if is_mapped_drive else drive)


def _get_disk_partitions() -> Generator[DiskPartition]:
    for diskpart in psutil.disk_partitions(all=True):
        try:
            # Resolve converts any mapped drive to UNC paths (windows)
            yield DiskPartition(
                Path(diskpart.mountpoint).resolve(),
                Path(diskpart.device).resolve(),
                diskpart.fstype,
                diskpart.opts,
            )
        except OSError as e:
            logger.error(
                f"Unable to get information about {diskpart.mountpoint}. All files with that mountpoint as target will be skipped: {e!r}"
            )


async def _check_nt_network_drive(folder: Path) -> None:
    """Checks is the drive of this folder is a Windows network drive (UNC or unknown mapped drive) and exists.

    See: https://github.com/jbsparrow/CyberDropMediaItemer/issues/860
    """
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

    if folder_drive in _UNAVAILABLE:
        return

    mounts = tuple(p.mountpoint for p in _partitions())
    if folder_drive in mounts:
        return

    async with _LOCKS[folder_drive]:
        if folder_drive in _UNAVAILABLE or folder_drive in mounts:
            return

        logger.debug(f"Checking new possible network_drive: '{folder_drive}' for folder '{folder}'")

        try:
            is_dir = await asyncio.to_thread(folder_drive.is_dir)
        except OSError:
            is_dir = False

        if is_dir:
            _PARTITIONS.append(DiskPartition(folder_drive, folder_drive, "network_drive", ""))
            _get_mount_point.cache_clear()

        else:
            _UNAVAILABLE.add(folder_drive)
