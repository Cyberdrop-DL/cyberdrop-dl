from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
from contextvars import ContextVar
from typing import TYPE_CHECKING

from cyberdrop_dl.exceptions import InsufficientFreeSpaceError
from cyberdrop_dl.utils import enter_context

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable
    from pathlib import Path

    from cyberdrop_dl.url_objects import MediaItem

_REQUIRED_FREE_SPACE: ContextVar[int] = ContextVar("_REQUIRED_FREE_SPACE")


def _disk_usage(folder: Path) -> int:
    path = folder
    while True:
        try:
            return shutil.disk_usage(path).free
        except FileNotFoundError:
            if path.parent == path:
                return 0
            path = path.parent


try:
    from ._psutil import get_free_space as _get_free_space
    from ._psutil import start_loop as _psutil_loop
except ImportError:
    _psutil_loop = None

    async def _get_free_space(folder: Path) -> int:
        return await asyncio.to_thread(_disk_usage, folder)


async def has_sufficient_space(folder: Path, /, required_free_space: int | None = None) -> bool:
    free_space = await _get_free_space(folder)
    return free_space == -1 or free_space > (required_free_space or _REQUIRED_FREE_SPACE.get())


def create_free_space_checker(media_item: MediaItem, *, frequency: int = 5) -> Callable[[], Awaitable[None]]:
    current_chunk = 0

    async def checker() -> None:
        nonlocal current_chunk
        if current_chunk % frequency == 0 and not await has_sufficient_space(media_item.download_folder):
            raise InsufficientFreeSpaceError(media_item)

        current_chunk += 1

    return checker


@contextlib.asynccontextmanager
async def monitor(required_free_space: int) -> AsyncGenerator[None]:
    if _psutil_loop is None:
        logger.warning("psutil is not available on this system. Falling back to eager checks for free space")
        loop = None
    else:
        loop = asyncio.create_task(_psutil_loop(), name="storage monitor")
        await asyncio.sleep(0)
    try:
        with enter_context(_REQUIRED_FREE_SPACE, required_free_space):
            yield
    finally:
        if loop is not None:
            try:
                _ = loop.cancel("On monitor exit")
                await loop
            except asyncio.CancelledError:
                pass
