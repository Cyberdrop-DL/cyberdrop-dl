from __future__ import annotations

import asyncio
import contextlib
import itertools
import logging
import time
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from cyberdrop_dl import aio, constants, ffmpeg, storage
from cyberdrop_dl.clients import etag
from cyberdrop_dl.clients.response import AbstractResponse
from cyberdrop_dl.constants import FileExt
from cyberdrop_dl.exceptions import DownloadError, InvalidContentTypeError, SlowDownloadError
from cyberdrop_dl.utils import dates

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Coroutine, Mapping
    from pathlib import Path
    from typing import Any

    import aiohttp

    from cyberdrop_dl.clients.client import HTTPClient
    from cyberdrop_dl.config import Config
    from cyberdrop_dl.manager import Manager
    from cyberdrop_dl.progress import ProgressHook
    from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem


logger = logging.getLogger(__name__)


_CONTENT_TYPES_OVERRIDES: dict[str, str] = {"text/vnd.trolltech.linguist": "video/MP2T"}
_SLOW_DOWNLOAD_PERIOD: int = 10  # seconds
_FREE_SPACE_CHECK_PERIOD: int = 5  # Check every 5 chunks
_USE_IMPERSONATION: set[str] = {"vsco", "celebforum"}


class DownloadClient:
    """Low level class that performs the actual HTTP download operations"""

    def __init__(self, manager: Manager, client: HTTPClient) -> None:
        self.manager = manager
        self.client = client
        self.download_speed_threshold = self.manager.config.settings.runtime_options.slow_download_speed
        self._supports_ranges: bool = True

    async def _download(self, domain: str, media_item: MediaItem) -> bool:
        """Downloads a file."""
        downloaded_filename = await self.manager.database.history.get_downloaded_filename(domain, media_item)
        download_dir = self.get_download_dir(media_item)
        if media_item.is_segment:
            media_item.partial_file = media_item.path = download_dir / media_item.filename
        else:
            media_item.partial_file = download_dir / f"{downloaded_filename}{constants.TempExt.PART}"

        resume_point = 0
        if self._supports_ranges and media_item.partial_file and (size := await aio.get_size(media_item.partial_file)):
            resume_point = size
            media_item.headers["Range"] = f"bytes={size}-"

        await asyncio.sleep(self.manager.config.global_settings.rate_limiting_options.total_delay)

        def process_response(resp: aiohttp.ClientResponse | AbstractResponse[Any]):
            return self._process_response(media_item, domain, resume_point, resp)

        return await self._request_download(media_item, process_response)

    async def _process_response(
        self,
        media_item: MediaItem,
        domain: str,
        resume_point: int,
        resp: aiohttp.ClientResponse | AbstractResponse[Any],
    ) -> bool:
        if resp.status == HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE:
            await aio.unlink(media_item.partial_file)

        etag.check(resp.headers)
        await self.client.check_http_status(resp)

        if not media_item.is_segment:
            _ = get_content_type(media_item.ext, resp.headers)

        media_item.filesize = int(resp.headers.get("Content-Length", "0")) or None
        if not media_item.path:
            proceed, skip = await self.get_final_file_info(media_item, domain)
            _check_content_length(resp.headers)
            if skip:
                self.manager.scrape_mapper.tui.files.stats.skipped += 1
                return False
            if not proceed:
                if media_item.is_segment:
                    return True
                logger.info(f"Skipping {media_item.url} as it has already been downloaded")
                self.manager.scrape_mapper.tui.files.stats.previously_completed += 1
                await self.process_completed(media_item, domain)
                await self.handle_media_item_completion(media_item, downloaded=False)

                return False

        if resp.status != HTTPStatus.PARTIAL_CONTENT:
            await aio.unlink(media_item.partial_file, missing_ok=True)

        if (
            not media_item.is_segment
            and not media_item.uploaded_at
            and (last_modified := get_last_modified(resp.headers))
        ):
            logger.warning(
                f"Unable to parse upload date for {media_item.url}, using `Last-Modified` header as file datetime"
            )
            media_item.uploaded_at = last_modified

        if media_item.is_segment:
            hook = self.manager.scrape_mapper.tui.downloads.download_hls_seg()

        else:
            size = (media_item.filesize + resume_point) if media_item.filesize is not None else None
            hook = self.manager.scrape_mapper.tui.downloads.download_file(
                media_item.filename,
                media_item.domain,
                size,
            )

        if resume_point:
            hook.advance(resume_point)

        with hook:
            await self._append_content(media_item, hook, self._get_resp_reader(resp))
        return True

    def _get_resp_reader(
        self, resp: aiohttp.ClientResponse | AbstractResponse[Any]
    ) -> AbstractResponse[Any] | aiohttp.StreamReader:
        if isinstance(resp, AbstractResponse):
            return resp
        return resp.content

    @contextlib.asynccontextmanager
    async def __request_context(
        self, url: AbsoluteHttpURL, domain: str, headers: dict[str, str]
    ) -> AsyncGenerator[AbstractResponse[Any] | aiohttp.ClientResponse]:
        if domain in _USE_IMPERSONATION:
            resp = await self.client.curl_session.get(str(url), stream=True, headers=headers)
            try:
                yield AbstractResponse.create(resp)
            finally:
                await resp.aclose()
            return

        async with self.client._download_session.get(url, headers=headers) as resp:
            yield resp

    async def _request_download(
        self,
        media_item: MediaItem,
        process_response: Callable[[aiohttp.ClientResponse | AbstractResponse[Any]], Coroutine[None, None, bool]],
    ) -> bool:
        async with self.__request_context(media_item.real_url, media_item.domain, media_item.headers) as resp:
            return await process_response(resp)

    async def _append_content(
        self,
        media_item: MediaItem,
        hook: ProgressHook,
        content: aiohttp.StreamReader | AbstractResponse[Any],
    ) -> None:
        """Appends content to a file."""

        check_free_space = storage.create_free_space_checker(media_item)
        check_download_speed = make_speed_checker(media_item, hook, self.download_speed_threshold)
        await check_free_space()
        await self._pre_download_check(media_item)

        async with aio.open(media_item.partial_file, mode="ab") as f:
            async for chunk in content.iter_chunked(self.client.chunk_size):
                await check_free_space()
                chunk_size = len(chunk)
                await self.client.speed_limiter.acquire(chunk_size)
                await f.write(chunk)
                hook.advance(chunk_size)
                check_download_speed()

        await self._post_download_check(media_item)

    @aio.to_thread
    def _pre_download_check(self, media_item: MediaItem) -> None:
        media_item.partial_file.parent.mkdir(parents=True, exist_ok=True)
        if not media_item.partial_file.is_file():
            media_item.partial_file.touch()

    async def _post_download_check(self, media_item: MediaItem, *_) -> None:
        if not await aio.get_size(media_item.partial_file):
            await aio.unlink(media_item.partial_file, missing_ok=True)
            raise DownloadError(HTTPStatus.INTERNAL_SERVER_ERROR, message="File is empty")

    async def download_file(self, domain: str, media_item: MediaItem) -> bool:
        """Starts a file."""
        if self.manager.config.settings.download_options.skip_download_mark_completed and not media_item.is_segment:
            logger.info(f"Download removed {media_item.url} due to mark completed option")
            self.manager.scrape_mapper.tui.files.stats.skipped += 1
            # set completed path
            await self.process_completed(media_item, domain)
            return False

        downloaded = await self._download(domain, media_item)

        if downloaded:
            await aio.move(media_item.partial_file, media_item.path)
            if not media_item.is_segment:
                proceed = not await filter_by_duration(media_item, self.manager.config)
                await self.manager.database.history.add_duration(domain, media_item)
                if not proceed:
                    logger.info(f"Download skipped {media_item.url} due to runtime restrictions")
                    await aio.unlink(media_item.path)
                    await self.mark_incomplete(media_item, domain)
                    self.manager.scrape_mapper.tui.files.stats.skipped += 1
                    return False
                await self.process_completed(media_item, domain)
                await self.handle_media_item_completion(media_item, downloaded=True)
        return downloaded

    """~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"""

    async def mark_incomplete(self, media_item: MediaItem, domain: str) -> None:
        """Marks the media item as incomplete in the database."""
        if media_item.is_segment:
            return
        await self.manager.database.history.insert_incompleted(domain, media_item)

    async def process_completed(self, media_item: MediaItem, domain: str) -> None:
        """Marks the media item as completed in the database and adds to the completed list."""
        await self.mark_completed(domain, media_item)
        await self.add_file_size(domain, media_item)

    async def mark_completed(self, domain: str, media_item: MediaItem) -> None:
        await self.manager.database.history.mark_complete(domain, media_item)

    async def add_file_size(self, domain: str, media_item: MediaItem) -> None:
        if not media_item.path:
            media_item.path = self.get_file_location(media_item)
        if await aio.is_file(media_item.path):
            await self.manager.database.history.add_filesize(domain, media_item)

    async def handle_media_item_completion(self, media_item: MediaItem, downloaded: bool = False) -> None:
        """Sends to hash client to handle hashing and marks as completed/current download."""
        try:
            media_item.downloaded = downloaded
            await self.manager.hasher.hash_item_during_download(media_item)
            self.manager.add_completed(media_item)
        except Exception:
            logger.exception(f"Error handling media item completion of: {media_item.path}")

    """~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"""

    def get_download_dir(self, media_item: MediaItem) -> Path:
        """Returns the download directory for the media item."""
        download_folder = media_item.download_folder
        if self.manager.cli_args.retry_any:
            return download_folder

        if self.manager.config.settings.download_options.block_download_sub_folders:
            while download_folder.parent != self.manager.config.settings.files.download_folder:
                download_folder = download_folder.parent
            media_item.download_folder = download_folder
        return download_folder

    def get_file_location(self, media_item: MediaItem) -> Path:
        download_dir = self.get_download_dir(media_item)
        return download_dir / media_item.filename

    async def get_final_file_info(self, media_item: MediaItem, domain: str) -> tuple[bool, bool]:
        """Complicated checker for if a file already exists, and was already downloaded."""
        media_item.path = self.get_file_location(media_item)
        part_suffix = media_item.path.suffix + constants.TempExt.PART
        media_item.partial_file = media_item.path.with_suffix(part_suffix)

        expected_size = media_item.filesize
        proceed = True
        skip = False

        while True:
            if expected_size and not media_item.is_segment:
                file_size_check = self.check_filesize_limits(media_item)
                if not file_size_check:
                    logger.info(f"Download skipped {media_item.url} due to filesize restrictions")
                    proceed = False
                    skip = True
                    return proceed, skip

            if not media_item.path.exists() and not media_item.partial_file.exists():
                break

            if media_item.path.exists() and media_item.path.stat().st_size == media_item.filesize:
                logger.info(f"Found {media_item.path.name} locally, skipping download")
                proceed = False
                break

            downloaded_filename = await self.manager.database.history.get_downloaded_filename(
                domain,
                media_item,
            )
            if not downloaded_filename:
                media_item.path, media_item.partial_file = await self.iterate_filename(
                    media_item.path,
                    media_item,
                )
                break

            if media_item.filename == downloaded_filename:
                if media_item.partial_file.exists():
                    logger.info(f"Found {downloaded_filename} locally, trying to resume")
                    assert media_item.filesize
                    size = media_item.partial_file.stat().st_size
                    if size >= media_item.filesize:
                        logger.info(f"Deleting partial file {media_item.partial_file}. Size is out of bound")
                        media_item.partial_file.unlink()

                    elif size == media_item.filesize:
                        if media_item.path.exists():
                            logger.warning(
                                f"Found conflicting complete file '{media_item.path}' locally, iterating filename"
                            )
                            new_complete_filename, new_partial_file = await self.iterate_filename(
                                media_item.path,
                                media_item,
                            )
                            media_item.partial_file.rename(new_complete_filename)
                            proceed = False

                            media_item.path = new_complete_filename
                            media_item.partial_file = new_partial_file
                        else:
                            proceed = False
                            media_item.partial_file.rename(media_item.path)
                        logger.info(
                            f"Renaming found partial file '{media_item.partial_file}' to complete file {media_item.path}"
                        )
                elif media_item.path.exists():
                    if media_item.path.stat().st_size == media_item.filesize:
                        logger.info(f"Found complete file '{media_item.path}' locally, skipping download")
                        proceed = False
                    else:
                        logger.warning(
                            f"Found conflicting complete file '{media_item.path}' locally, iterating filename"
                        )
                        media_item.path, media_item.partial_file = await self.iterate_filename(
                            media_item.path,
                            media_item,
                        )
                break

            media_item.filename = downloaded_filename
        media_item.download_filename = media_item.path.name
        await self.manager.database.history.add_download_filename(domain, media_item)
        return proceed, skip

    async def iterate_filename(self, complete_file: Path, media_item: MediaItem) -> tuple[Path, Path]:
        """Iterates the filename until it is unique."""
        part_suffix = complete_file.suffix + constants.TempExt.PART
        partial_file = complete_file.with_suffix(part_suffix)
        for iteration in itertools.count(1):
            filename = f"{complete_file.stem} ({iteration}){complete_file.suffix}"
            temp_complete_file = media_item.download_folder / filename
            if not temp_complete_file.exists() and not await self.manager.database.history.check_filename_exists(
                filename
            ):
                media_item.filename = filename
                complete_file = media_item.download_folder / media_item.filename
                partial_file = complete_file.with_suffix(part_suffix)
                break
        return complete_file, partial_file

    def check_filesize_limits(self, media: MediaItem) -> bool:
        """Checks if the file size is within the limits."""
        limits = self.manager.config.settings.file_size_limits.ranges

        assert media.filesize is not None
        if media.ext in FileExt.IMAGE:
            return media.filesize in limits.image
        if media.ext in FileExt.VIDEO:
            return media.filesize in limits.video

        return media.filesize in limits.other


def get_content_type(ext: str, headers: Mapping[str, str]) -> str | None:
    content_type: str = headers.get("Content-Type", "")
    content_length = headers.get("Content-Length")
    if not content_type and not content_length:
        msg = "No content type in response headers"
        raise InvalidContentTypeError(message=msg)

    if not content_type:
        return None

    override_key = next((name for name in _CONTENT_TYPES_OVERRIDES if name in content_type), "<NO_OVERRIDE>")
    override: str | None = _CONTENT_TYPES_OVERRIDES.get(override_key)
    content_type = override or content_type
    content_type = content_type.lower()

    if is_html_or_text(content_type) and ext.lower() not in FileExt.TEXT:
        msg = f"Received '{content_type}', was expecting other"
        raise InvalidContentTypeError(message=msg)

    return content_type


def get_last_modified(headers: Mapping[str, str]) -> int | None:
    if date_str := headers.get("Last-Modified"):
        return dates.parse_http(date_str)


def is_html_or_text(content_type: str) -> bool:
    return any(s in content_type for s in ("html", "text"))


def _check_content_length(headers: Mapping[str, Any]) -> None:
    content_length, content_type = headers.get("Content-Length"), headers.get("Content-Type")
    if content_length is None or content_type is None:
        return
    if content_length == "322509" and content_type == "video/mp4":
        raise DownloadError(status="Bunkr Maintenance", message="Bunkr under maintenance")
    if content_length == "73003" and content_type == "video/mp4":
        raise DownloadError(410)  # Placeholder video with text "Video removed" (efukt)


async def filter_by_duration(media_item: MediaItem, config: Config) -> bool:
    if media_item.is_segment:
        return False

    is_video = media_item.ext.lower() in FileExt.VIDEO
    is_audio = media_item.ext.lower() in FileExt.AUDIO
    if not (is_video or is_audio):
        return False

    duration_limits = config.settings.media_duration_limits.ranges
    duration: float | None = await _probe_duration(media_item)
    media_item.duration = duration

    if duration is None:
        return False

    if is_video:
        return duration not in duration_limits.video

    return duration not in duration_limits.audio


async def _probe_duration(media_item: MediaItem) -> float | None:
    if media_item.duration:
        return media_item.duration

    if media_item.downloaded:
        properties = await ffmpeg.probe(media_item.path)

    else:
        properties = await ffmpeg.probe(media_item.url, headers=media_item.headers)

    if properties.format.duration:
        return properties.format.duration
    if properties.video:
        return properties.video.duration
    if properties.audio:
        return properties.audio.duration


def make_speed_checker(media_item: MediaItem, hook: ProgressHook, speed_threshold: int) -> Callable[[], None]:
    last_slow_speed_read = None

    def check_download_speed() -> None:
        nonlocal last_slow_speed_read
        if not speed_threshold:
            return

        speed = hook.get_speed()
        if speed > speed_threshold:
            last_slow_speed_read = None
        elif not last_slow_speed_read:
            last_slow_speed_read = time.perf_counter()
        elif time.perf_counter() - last_slow_speed_read > _SLOW_DOWNLOAD_PERIOD:
            raise SlowDownloadError(origin=media_item)

    return check_download_speed
