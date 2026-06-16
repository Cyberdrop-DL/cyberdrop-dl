from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import os
from typing import TYPE_CHECKING

from aiohttp import ClientConnectorError, ClientError, ClientResponseError

from cyberdrop_dl import aio, constants, ffmpeg, storage
from cyberdrop_dl.clients.downloads import filter_by_duration
from cyberdrop_dl.downloader import hls
from cyberdrop_dl.exceptions import (
    DownloadError,
    DurationError,
    InsufficientFreeSpaceError,
    InvalidContentTypeError,
    RestrictedDateRangeError,
    RestrictedFiletypeError,
    SkipDownloadError,
)
from cyberdrop_dl.utils import dates, error_handling_wrapper

if TYPE_CHECKING:
    import datetime
    from collections.abc import AsyncGenerator

    from cyberdrop_dl.clients.downloads import DownloadClient
    from cyberdrop_dl.config import Config
    from cyberdrop_dl.manager import Manager
    from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem
    from cyberdrop_dl.utils.m3u8 import Rendition

logger = logging.getLogger(__name__)


_KNOWN_BAD_URLS = {
    "https://i.imgur.com/removed.png": 404,
    "https://saint2.su/assets/notfound.gif": 404,
    "https://bnkr.b-cdn.net/maintenance-vid.mp4": 503,
    "https://bnkr.b-cdn.net/maintenance.mp4": 503,
    "https://c.bunkr-cache.se/maintenance-vid.mp4": 503,
    "https://c.bunkr-cache.se/maintenance.jpg": 503,
}


_GENERIC_CRAWLERS = ".", "no_crawler"
_FILE_LOCKS: aio.WeakAsyncLocks[str] = aio.WeakAsyncLocks()
_NULL_CONTEXT: contextlib.nullcontext[None] = contextlib.nullcontext()


@contextlib.asynccontextmanager
async def _exclusive_lock(media_item: MediaItem) -> AsyncGenerator[None]:
    async with _FILE_LOCKS[media_item.filename]:
        logger.debug(f"Lock for '{media_item.filename}' acquired")
        try:
            yield
        finally:
            logger.debug(f"Lock for '{media_item.filename}' released")


@dataclasses.dataclass(slots=True)
class Downloader:
    """Hight level class that handles limiters, database checks, skip by config checks and retries"""

    manager: Manager
    log_prefix: str = "Download"
    use_server_lock: bool = False
    max_attempts: int = dataclasses.field(init=False)

    _slots: int | None = None
    _waiting_items: int = dataclasses.field(init=False, default=0)
    _processed_items: set[str] = dataclasses.field(init=False, default_factory=set)
    _current_attempt_filesize: dict[str, int] = dataclasses.field(init=False, default_factory=dict)
    _semaphore: asyncio.Semaphore = dataclasses.field(init=False)
    _server_locks: aio.WeakAsyncLocks[str] = dataclasses.field(
        init=False, default_factory=aio.WeakAsyncLocks, repr=False
    )

    def __post_init__(self) -> None:
        self.slots = self._slots
        self.max_attempts = self.config.downloads.attempts

    @property
    def waiting_items(self) -> int:
        return self._waiting_items

    @property
    def slots(self) -> int | None:
        return self._slots

    @slots.setter
    def slots(self, new_limit: int | None) -> None:
        try:
            sem = self._semaphore
        except AttributeError:
            pass
        else:
            if not (sem._waiters is None and sem._value == self._slots):
                raise RuntimeError("Can't change download limits. Downloader is already in use")

        upper_limit = self.config.downloads.concurrency_per_domain
        self._slots = min(new_limit or upper_limit, upper_limit)
        self._semaphore = asyncio.Semaphore(self._slots)

    @property
    def client(self) -> DownloadClient:
        return self.manager.download_client

    @property
    def config(self) -> Config:
        return self.manager.config

    @property
    def _ignore_history(self) -> bool:
        return self.manager.config.ignore_history

    @error_handling_wrapper
    async def __download_w_retries(self, media_item: MediaItem) -> bool:
        while True:
            try:
                return bool(await self.__download_file(media_item))

            except DownloadError as e:
                if not e.retry:
                    raise

                logger.error(f"{self.log_prefix} failed: {media_item.url} with error: {e!s}")
                if media_item.attempts >= self.max_attempts:
                    raise

                logger.info(
                    f"Retrying {self.log_prefix.lower()}: {media_item.url}, retry attempt: {media_item.attempts + 1}"
                )

    async def __finalize_download(self, media_item: MediaItem) -> None:
        await aio.chmod(media_item.path, 0o666)
        if media_item.is_segment:
            return
        await _set_mtime(media_item, self.config)
        self.manager.scrape_mapper.tui.files.stats.completed += 1
        logger.info(f"Download finished: {media_item.url}")

    async def _check_skip_by_config(self, media_item: MediaItem) -> None:
        if not _is_allowed_filetype(media_item, self.config):
            raise RestrictedFiletypeError(origin=media_item)
        if not _is_allowed_date_range(media_item, self.config):
            raise RestrictedDateRangeError(origin=media_item)
        if not await storage.has_sufficient_space(media_item.download_folder):
            raise InsufficientFreeSpaceError(media_item)
        if await filter_by_duration(media_item, self.config):
            await self.manager.database.history.add_duration(media_item.domain, media_item)
            raise DurationError(origin=media_item)

    async def _download(self, media_item: MediaItem) -> bool:
        if not media_item.is_segment:
            logger.info(f"{self.log_prefix} starting: {media_item.url}")

        async with _exclusive_lock(media_item):
            return bool(await self.__download_w_retries(media_item))

    @contextlib.asynccontextmanager
    async def __download_context(self, media_item: MediaItem) -> AsyncGenerator[None]:
        await self.client.mark_incomplete(media_item, media_item.domain)
        if media_item.is_segment:
            yield
            return

        self._waiting_items += 1
        async with self.lock(media_item.real_url):
            self._processed_items.add(media_item.db_path)
            self._waiting_items -= 1
            yield

    async def __download_file(self, media_item: MediaItem) -> bool | None:
        _check_url(media_item)
        media_item.attempts += 1
        try:
            if not media_item.is_segment:
                media_item.duration = await self.manager.database.history.get_duration(media_item.domain, media_item)
                await self._check_skip_by_config(media_item)
            downloaded = await self.client.download_file(media_item.domain, media_item)

        except SkipDownloadError as e:
            if not media_item.is_segment:
                logger.info(f"Download skipped {media_item.url}: {e}")
                self.manager.scrape_mapper.tui.files.stats.skipped += 1

        except (DownloadError, ClientResponseError, InvalidContentTypeError):
            raise

        except (
            ConnectionResetError,
            FileNotFoundError,
            PermissionError,
            TimeoutError,
            ClientError,
            ClientConnectorError,
        ) as e:
            ui_message = getattr(e, "status", type(e).__name__)
            if media_item.partial_file and (size := await aio.get_size(media_item.partial_file)):
                if self._current_attempt_filesize.get(media_item.filename, 0) >= size:
                    raise DownloadError(ui_message, message=f"{self.log_prefix} failed", retry=True) from None

                self._current_attempt_filesize[media_item.filename] = size
                raise DownloadError(status=999, message="Download timeout reached, retrying", retry=True) from None

            raise DownloadError(ui_message, str(e), retry=True) from e

        else:
            if downloaded:
                await self.__finalize_download(media_item)
            return downloaded

    @contextlib.asynccontextmanager
    async def lock(self, url: AbsoluteHttpURL) -> AsyncGenerator[None]:
        server_lock = self._server_locks[url.host] if self.use_server_lock else _NULL_CONTEXT
        async with (
            server_lock,
            self._semaphore,
            self.manager.http_client.global_download_limiter,
        ):
            yield

    async def run(self, media_item: MediaItem) -> bool:
        if media_item.url.path in self._processed_items and not self._ignore_history:
            return False

        async with self.__download_context(media_item):
            return await self._download(media_item)

    @error_handling_wrapper
    async def download_hls(self, media_item: MediaItem, m3u8_group: Rendition) -> None:
        if media_item.url.path in self._processed_items and not self._ignore_history:
            return

        assert ffmpeg.is_installed()
        async with self.__download_context(media_item):
            await self.__hls_download(media_item, m3u8_group)

    async def __hls_download(self, media_item: MediaItem, rendition: Rendition) -> None:
        media_item.path = media_item.download_folder / media_item.filename
        media_item.download_filename = media_item.path.name
        await self.manager.database.history.add_download_filename(media_item.domain, media_item)

        with self.manager.scrape_mapper.tui.downloads.download_hls(
            media_item.filename,
            media_item.domain,
            segments=sum(len(m.segments) for m in rendition if m is not None),
            url=media_item.url,
        ):
            await self._hls_download(media_item, rendition)

    async def _hls_download(self, media_item: MediaItem, rendition: Rendition) -> None:
        streams = await hls.download(media_item, rendition, self._download)
        if not streams.audio:
            await aio.move(streams.video, media_item.path)

        else:
            # TODO: add remux method to ffmpeg to create an mkv file instead of mp4
            # Subtitles format may be incompatible with mp4 and they will be silently dropped by ffmpeg
            # so we leave them as independent files for now
            logger.debug(f"Merging audio and video stream from {media_item.real_url}")
            ffmpeg_result = await ffmpeg.merge((streams.video, streams.audio), media_item.path)

            if not ffmpeg_result.success:
                raise DownloadError("FFmpeg Concat Error", ffmpeg_result.stderr, media_item)

        await self.client.process_completed(media_item, media_item.domain)
        await self.client.handle_media_item_completion(media_item, downloaded=True)
        await self.__finalize_download(media_item)


def _is_allowed_filetype(media_item: MediaItem, config: Config) -> bool:
    filters = config.filters.files
    ext = media_item.ext.lower()

    for is_allowed, valid_exts in [
        (filters.images, constants.FileExt.IMAGE),
        (filters.videos, constants.FileExt.VIDEO),
        (filters.audio, constants.FileExt.AUDIO),
    ]:
        if ext in valid_exts:
            return is_allowed

    return filters.non_media


def _is_allowed_date_range(media_item: MediaItem, config: Config) -> bool:
    if not media_item.uploaded_at_date:
        return True

    return _filter_by_date(media_item.uploaded_at_date, config)


def _filter_by_date(item_datetime: datetime.datetime, config: Config) -> bool:
    item_date = item_datetime.date()
    filters = config.filters

    if filters.before and item_date > filters.before:
        return False
    return not (filters.after and item_date < filters.after)


async def _set_mtime(media_item: MediaItem, config: Config) -> None:
    if media_item.is_segment:
        return

    if not config.mtime:
        return

    if not media_item.uploaded_at:
        logger.warning(f"Unable to parse upload date for {media_item.url}, using current datetime as file datetime")
        return

    # 1. try setting creation date
    await dates.set_creation_time(media_item.path, media_item.uploaded_at)

    # 2. try setting modification and access date
    try:
        await asyncio.to_thread(os.utime, media_item.path, (media_item.uploaded_at, media_item.uploaded_at))
    except OSError:
        pass


def _check_url(media_item: MediaItem) -> None:
    url_as_str = str(media_item.url)
    if url_as_str in _KNOWN_BAD_URLS:
        raise DownloadError(_KNOWN_BAD_URLS[url_as_str])
