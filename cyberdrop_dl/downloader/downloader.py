from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from dataclasses import field
from typing import TYPE_CHECKING, NamedTuple

from aiohttp import ClientConnectorError, ClientError, ClientResponseError

from cyberdrop_dl import aio, constants, ffmpeg, storage
from cyberdrop_dl.exceptions import (
    DownloadError,
    DurationError,
    ErrorLogMessage,
    InsufficientFreeSpaceError,
    InvalidContentTypeError,
    RestrictedDateRangeError,
    RestrictedFiletypeError,
    SkipDownloadError,
    TooManyCrawlerErrors,
)
from cyberdrop_dl.url_objects import HlsSegment, MediaItem
from cyberdrop_dl.utils import dates, error_handling_wrapper, parse_url

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from cyberdrop_dl.clients.download_client import DownloadClient
    from cyberdrop_dl.managers.manager import Manager
    from cyberdrop_dl.utils.m3u8 import M3U8, Rendition


class SegmentDownloadResult(NamedTuple):
    item: MediaItem
    downloaded: bool


KNOWN_BAD_URLS = {
    "https://i.imgur.com/removed.png": 404,
    "https://saint2.su/assets/notfound.gif": 404,
    "https://bnkr.b-cdn.net/maintenance-vid.mp4": 503,
    "https://bnkr.b-cdn.net/maintenance.mp4": 503,
    "https://c.bunkr-cache.se/maintenance-vid.mp4": 503,
    "https://c.bunkr-cache.se/maintenance.jpg": 503,
}


GENERIC_CRAWLERS = ".", "no_crawler"


class Downloader:
    def __init__(self, manager: Manager, domain: str) -> None:
        self.manager: Manager = manager
        self.domain: str = domain

        self.client: DownloadClient = field(init=False)
        self.log_prefix = "Download attempt (unsupported domain)" if domain in GENERIC_CRAWLERS else "Download"
        self.processed_items: set[str] = set()
        self.waiting_items = 0

        self._additional_headers = {}
        self._current_attempt_filesize: dict[str, int] = {}
        self._file_lock_vault = manager.client_manager.file_locks
        self._ignore_history = manager.config.settings.runtime_options.ignore_history
        self._semaphore: asyncio.Semaphore = field(init=False)

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
                    f"Retrying {self.log_prefix.lower()}: {media_item.url} , retry attempt: {media_item.attempts + 1}"
                )

    @property
    def max_attempts(self):
        if self.manager.config.settings.download_options.disable_download_attempt_limit:
            return 1
        return self.manager.config.global_settings.rate_limiting_options.download_attempts

    def startup(self) -> None:
        """Starts the downloader."""
        self.client = self.manager.client_manager.download_client
        self._semaphore = asyncio.Semaphore(self.manager.client_manager.get_download_slots(self.domain))

        self.manager.config.settings.files.download_folder.mkdir(parents=True, exist_ok=True)
        if self.manager.config.settings.sorting.sort_downloads:
            self.manager.config.settings.sorting.sort_folder.mkdir(parents=True, exist_ok=True)

    @contextlib.asynccontextmanager
    async def _download_context(self, media_item: MediaItem):

        media_item.attempts = 0
        await self.client.mark_incomplete(media_item, self.domain)
        if media_item.is_segment:
            yield
            return

        self.waiting_items += 1

        server = (media_item.debrid_link or media_item.url).host
        server_limit, domain_limit, global_limit = (
            self.client.server_limiter(media_item.domain, server),
            self._semaphore,
            self.manager.client_manager.global_download_slots,
        )

        async with server_limit, domain_limit, global_limit:
            self.processed_items.add(media_item.db_path)
            self.waiting_items -= 1
            yield

    async def run(self, media_item: MediaItem) -> bool:
        """Runs the download loop."""

        if media_item.url.path in self.processed_items and not self._ignore_history:
            return False

        async with self._download_context(media_item):
            return await self.start_download(media_item)

    @error_handling_wrapper
    async def download_hls(self, media_item: MediaItem, m3u8_group: Rendition) -> None:
        if media_item.url.path in self.processed_items and not self._ignore_history:
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
        if not self.manager.client_manager.is_allowed_filetype(media_item):
            raise RestrictedFiletypeError(origin=media_item)
        if not await self.manager.client_manager.check_file_duration(media_item):
            raise DurationError(origin=media_item)
        if not self.manager.client_manager.check_allowed_date_range(media_item):
            raise RestrictedDateRangeError(origin=media_item)

    async def set_file_datetime(self, media_item: MediaItem, complete_file: Path) -> None:
        """Sets the file's datetime."""
        if media_item.is_segment:
            return

        if self.manager.config.settings.download_options.disable_file_timestamps:
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

    """~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"""

    async def start_download(self, media_item: MediaItem) -> bool:
        try:
            self.client.client_manager.check_domain_errors(self.domain)
        except TooManyCrawlerErrors:
            return False

        if not media_item.is_segment:
            logger.info(f"{self.log_prefix} starting: {media_item.url}")

        async with self._file_lock_vault[media_item.filename]:
            logger.debug(f"Lock for '{media_item.filename}' acquired")
            try:
                return bool(await self.download(media_item))
            finally:
                logger.debug(f"Lock for '{media_item.filename}' released")

    async def _download(self, media_item: MediaItem) -> bool | None:
        """Downloads the media item."""
        url_as_str = str(media_item.url)
        if url_as_str in KNOWN_BAD_URLS:
            raise DownloadError(KNOWN_BAD_URLS[url_as_str])
        try:
            self.client.client_manager.check_domain_errors(self.domain)
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

    def write_download_error(
        self,
        media_item: MediaItem,
        error_log_msg: ErrorLogMessage,
        exc_info: Exception | None = None,
    ) -> None:
        logger.error(
            f"{self.log_prefix} Failed: {media_item.url} ({error_log_msg.main_log_msg}) \n -> Referer: {media_item.referer}",
            exc_info=exc_info,
        )
        self.manager.logs.write_download_error(media_item, error_log_msg.csv_log_msg)
        self.manager.scrape_mapper.tui.files.stats.failed += 1
        self.manager.scrape_mapper.tui.download_errors.add(error_log_msg.ui_failure)
