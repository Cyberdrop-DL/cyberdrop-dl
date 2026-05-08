from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import os
from typing import TYPE_CHECKING, NamedTuple

from aiohttp import ClientConnectorError, ClientError, ClientResponseError

from cyberdrop_dl import aio, constants, ffmpeg, storage
from cyberdrop_dl.clients.download_client import filter_by_duration
from cyberdrop_dl.exceptions import (
    DownloadError,
    DurationError,
    InsufficientFreeSpaceError,
    InvalidContentTypeError,
    RestrictedDateRangeError,
    RestrictedFiletypeError,
    SkipDownloadError,
)
from cyberdrop_dl.url_objects import HlsSegment, MediaItem
from cyberdrop_dl.utils import dates, error_handling_wrapper, parse_url

if TYPE_CHECKING:
    import datetime
    from collections.abc import AsyncGenerator, Generator
    from pathlib import Path

    from cyberdrop_dl.clients.download_client import DownloadClient
    from cyberdrop_dl.config import Config
    from cyberdrop_dl.manager import Manager
    from cyberdrop_dl.utils.m3u8 import M3U8, Rendition

logger = logging.getLogger(__name__)


class SegmentDownloadResult(NamedTuple):
    item: MediaItem
    downloaded: bool


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
    domain: str
    log_prefix: str = "Download"
    download_slots: int | None = None
    use_server_lock: bool = False

    waiting_items: int = dataclasses.field(init=False, default=0)

    _processed_items: set[str] = dataclasses.field(init=False, default_factory=set)
    _current_attempt_filesize: dict[str, int] = dataclasses.field(init=False, default_factory=dict)
    _semaphore: asyncio.Semaphore = dataclasses.field(init=False)
    _server_locks: aio.WeakAsyncLocks[str] = dataclasses.field(init=False, default_factory=aio.WeakAsyncLocks)

    def __post_init__(self) -> None:
        upper_limit = self.config.global_settings.rate_limiting_options.max_simultaneous_downloads_per_domain
        self._semaphore = asyncio.Semaphore(min(self.download_slots or upper_limit, upper_limit))

    @property
    def client(self) -> DownloadClient:
        return self.manager.http_client.download_client

    @property
    def config(self) -> Config:
        return self.manager.config

    @property
    def _ignore_history(self) -> bool:
        return self.manager.config.settings.runtime_options.ignore_history

    @property
    def max_attempts(self) -> int:
        if self.config.settings.download_options.disable_download_attempt_limit:
            return 1
        return self.config.global_settings.rate_limiting_options.download_attempts

    def _server_lock(self, server: str) -> asyncio.Lock | contextlib.nullcontext[None]:
        if self.use_server_lock:
            return self._server_locks[server]
        return _NULL_CONTEXT

    @error_handling_wrapper
    async def download(self, media_item: MediaItem) -> bool:
        while True:
            try:
                return bool(await self._download(media_item))

            except DownloadError as e:
                if not e.retry:
                    raise

                if e.status != 999:
                    media_item.attempts += 1

                logger.error(f"{self.log_prefix} failed: {media_item.url} with error: {e!s}")
                if media_item.attempts >= self.max_attempts:
                    raise

                logger.info(
                    f"Retrying {self.log_prefix.lower()}: {media_item.url}, retry attempt: {media_item.attempts + 1}"
                )

    @contextlib.asynccontextmanager
    async def _download_context(self, media_item: MediaItem):

        media_item.attempts = 0
        await self.client.mark_incomplete(media_item, self.domain)
        if media_item.is_segment:
            yield
            return

        self.waiting_items += 1

        server = (media_item.debrid_link or media_item.url).host
        async with (
            self._server_lock(server),
            self._semaphore,
            self.manager.http_client.global_download_limiter,
        ):
            self._processed_items.add(media_item.db_path)
            self.waiting_items -= 1
            yield

    async def run(self, media_item: MediaItem) -> bool:
        """Runs the download loop."""

        if media_item.url.path in self._processed_items and not self._ignore_history:
            return False

        async with self._download_context(media_item):
            return await self.start_download(media_item)

    @error_handling_wrapper
    async def download_hls(self, media_item: MediaItem, m3u8_group: Rendition) -> None:
        if media_item.url.path in self._processed_items and not self._ignore_history:
            return

        if not ffmpeg.is_installed():
            msg = "ffmpeg is not installed. (Required for HLS downloads)"
            if os.name == "nt":
                msg += ". Get it from: https://www.gyan.dev/ffmpeg/builds/"

            raise DownloadError("FFmpeg Error", msg, media_item)

        async with self._download_context(media_item):
            await self._start_hls_download(media_item, m3u8_group)

    async def _start_hls_download(self, media_item: MediaItem, m3u8_group: Rendition) -> None:
        media_item.path = media_item.download_folder / media_item.filename
        # TODO: register database duration from m3u8 info
        # TODO: compute approx size for UI from the m3u8 info
        media_item.download_filename = media_item.path.name
        await self.manager.database.history.add_download_filename(self.domain, media_item)

        with self.manager.scrape_mapper.tui.downloads.download_hls(
            media_item.filename,
            media_item.domain,
            segments=sum(len(m.segments) for m in m3u8_group if m is not None),
        ):
            video, audio, _subs = await self._download_rendition_group(media_item, m3u8_group)
            if not audio:
                await aio.move(video, media_item.path)
            else:
                # TODO: add remux method to ffmpeg to create an mkv file instead of mp4
                # Subtitles format may be incompatible with mp4 and they will be silently dropped by ffmpeg
                # so we leave them as independent files for now
                ffmpeg_result = await ffmpeg.merge((video, audio), media_item.path)

                if not ffmpeg_result.success:
                    raise DownloadError("FFmpeg Concat Error", ffmpeg_result.stderr, media_item)

            await self.client.process_completed(media_item, self.domain)
            await self.client.handle_media_item_completion(media_item, downloaded=True)
            await self.finalize_download(media_item, downloaded=True)

    async def _download_rendition_group(
        self, media_item: MediaItem, m3u8_group: Rendition
    ) -> tuple[Path, Path | None, Path | None]:

        temp_dir = media_item.path.with_suffix(constants.TempExt.HLS)

        async def download(m3u8: M3U8):
            assert m3u8.media_type
            if not m3u8.segments:
                raise DownloadError(204, f"{m3u8.media_type} m3u8 manifest ({m3u8.base_uri}) has no valid segments")

            download_folder = temp_dir / m3u8.media_type

            n_segmets = len(m3u8.segments)
            real_ext = parse_url(m3u8.segments[0].absolute_uri).suffix
            if n_segmets > 1:
                if m3u8.media_type == "subtitle":
                    suffix = f".{m3u8.media_type}{real_ext}"
                else:
                    suffix = f".{m3u8.media_type}.ts"
            else:
                suffix = media_item.path.suffix + real_ext

            output = media_item.path.with_suffix(suffix)
            if await aio.is_file(output):
                return output

            tasks_results = await self._download_segments(media_item, m3u8, download_folder)

            n_successful = sum(1 for result in tasks_results if result.downloaded)

            if n_successful != n_segmets:
                msg = f"Download of some segments failed. Successful: {n_successful:,}/{n_segmets:,} "
                raise DownloadError("HLS Seg Error", msg, media_item)

            seg_paths = [result.item.path for result in tasks_results]

            if n_segmets > 1:
                if m3u8.media_type == "subtitle":
                    await ffmpeg.merge_subs(seg_paths, output)
                else:
                    ffmpeg_result = await ffmpeg.concat(seg_paths, output, same_folder=False)
                    if not ffmpeg_result.success:
                        raise DownloadError("FFmpeg Concat Error", ffmpeg_result.stderr, media_item)
            else:
                _ = await asyncio.to_thread(seg_paths[0].rename, output)
            return output

        audio = subtitles = None
        if m3u8_group.subtitle:
            try:
                subtitles = await download(m3u8_group.subtitle)
            except Exception as e:
                logger.exception(f"Unable to download subtitles for {media_item.url}, Skipping. {e!r}")
            else:
                logger.warning(
                    f"Found subtitles for {media_item.url}, but CDL is currently unable to merge them. Subtitle were saved at {subtitles} "
                )

        if m3u8_group.audio:
            audio = await download(m3u8_group.audio)
        video = await download(m3u8_group.video)
        try:
            await aio.rmdir(temp_dir)
        except OSError:
            pass
        return video, audio, subtitles

    def _download_segments(self, media_item: MediaItem, m3u8: M3U8, download_folder: Path):
        padding = max(5, len(str(len(m3u8.segments))))

        def create_segments() -> Generator[HlsSegment]:
            for index, segment in enumerate(m3u8.segments, 1):
                assert segment.uri
                name = f"{index:0{padding}d}{constants.TempExt.HLS}"
                yield HlsSegment(segment.title, name, parse_url(segment.absolute_uri))

        async def download_segment(segment: HlsSegment):
            # TODO: segments download should bypass the downloads slots limits.
            # They count as a single download
            seg_media_item = MediaItem.from_item(
                media_item,
                segment.url,
                media_item.domain,
                db_path=media_item.db_path,
                download_folder=download_folder,
                filename=segment.name,
                ext=media_item.ext,
            )
            seg_media_item.is_segment = True
            seg_media_item.headers = media_item.headers.copy()
            return SegmentDownloadResult(
                seg_media_item,
                await self.start_download(seg_media_item),
            )

        return aio.map(
            download_segment,
            create_segments(),
            task_limit=10 if m3u8.media_type == "video" else 50,
        )

    async def finalize_download(self, media_item: MediaItem, downloaded: bool) -> None:
        if downloaded:
            await aio.chmod(media_item.path, 0o666)
            await self.set_file_datetime(media_item, media_item.path)
        self.manager.scrape_mapper.tui.files.stats.completed += 1
        logger.info(f"Download finished: {media_item.url}")

    """~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"""

    async def check_file_can_download(self, media_item: MediaItem) -> None:
        """Checks if the file can be downloaded."""
        if not await storage.has_sufficient_space(media_item.download_folder):
            raise InsufficientFreeSpaceError(media_item)
        if not _is_allowed_filetype(media_item, self.config):
            raise RestrictedFiletypeError(origin=media_item)
        if await filter_by_duration(media_item, self.config):
            await self.manager.database.history.add_duration(media_item.domain, media_item)
            raise DurationError(origin=media_item)
        if not _is_allowed_date_range(media_item, self.config):
            raise RestrictedDateRangeError(origin=media_item)

    async def set_file_datetime(self, media_item: MediaItem, complete_file: Path) -> None:
        """Sets the file's datetime."""
        if media_item.is_segment:
            return

        if self.config.settings.download_options.disable_file_timestamps:
            return
        if not media_item.uploaded_at:
            logger.warning(f"Unable to parse upload date for {media_item.url}, using current datetime as file datetime")
            return

        # 1. try setting creation date
        await dates.set_creation_time(complete_file, media_item.uploaded_at)

        # 2. try setting modification and access date
        try:
            await asyncio.to_thread(os.utime, complete_file, (media_item.uploaded_at, media_item.uploaded_at))
        except OSError:
            pass

    async def start_download(self, media_item: MediaItem) -> bool:
        if not media_item.is_segment:
            logger.info(f"{self.log_prefix} starting: {media_item.url}")

        async with _exclusive_lock(media_item):
            return bool(await self.download(media_item))

    async def _download(self, media_item: MediaItem) -> bool | None:
        """Downloads the media item."""
        url_as_str = str(media_item.url)
        if url_as_str in _KNOWN_BAD_URLS:
            raise DownloadError(_KNOWN_BAD_URLS[url_as_str])
        try:
            media_item.attempts = media_item.attempts or 1
            if not media_item.is_segment:
                media_item.duration = await self.manager.database.history.get_duration(self.domain, media_item)
                await self.check_file_can_download(media_item)
            downloaded = await self.client.download_file(self.domain, media_item)
            if downloaded:
                await aio.chmod(media_item.path, 0o666)
                if not media_item.is_segment:
                    await self.set_file_datetime(media_item, media_item.path)
                    self.manager.scrape_mapper.tui.files.stats.completed += 1
                    logger.info(f"Download finished: {media_item.url}")
            return downloaded

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

            message = str(e)
            raise DownloadError(ui_message, message, retry=True) from e


def _is_allowed_filetype(media_item: MediaItem, config: Config) -> bool:
    ignore_options = config.settings.ignore_options
    ext = media_item.ext.lower()

    return not (
        (ignore_options.exclude_images and ext in constants.FileExt.IMAGE)
        or (ignore_options.exclude_videos and ext in constants.FileExt.VIDEO)
        or (ignore_options.exclude_audio and ext in constants.FileExt.AUDIO)
        or (ignore_options.exclude_other and ext not in constants.FileExt.MEDIA)
    )


def _is_allowed_date_range(media_item: MediaItem, config: Config) -> bool:
    if not media_item.uploaded_at_date:
        return True

    return _filter_by_date(media_item.uploaded_at_date, config)


def _filter_by_date(item_datetime: datetime.datetime, config: Config) -> bool:
    item_date = item_datetime.date()
    ignore_options = config.settings.ignore_options

    if ignore_options.exclude_before and item_date < ignore_options.exclude_before:
        return False
    if ignore_options.exclude_after and item_date > ignore_options.exclude_after:
        return False
    return True
