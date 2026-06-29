from __future__ import annotations

import asyncio
import logging
from contextvars import ContextVar
from http import HTTPStatus
from typing import TYPE_CHECKING, NamedTuple

from cyberdrop_dl import aio, constants, ffmpeg
from cyberdrop_dl.exceptions import DownloadError
from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem
from cyberdrop_dl.utils import parse_url

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Generator, Iterable, Sequence
    from pathlib import Path

    from m3u8.model import InitializationSection, Segment

    from cyberdrop_dl.utils.m3u8 import M3U8, Rendition

    DownloadFn = Callable[[MediaItem], Awaitable[bool]]


CONCURRENT_SEGMENTS: ContextVar[int] = ContextVar("CONCURRENT_SEGMENTS")
logger = logging.getLogger(__name__)


class SegmentDownloadResult(NamedTuple):
    item: MediaItem
    downloaded: bool


class Streams(NamedTuple):
    video: Path
    audio: Path | None
    subs: Path | None


class HLSSegment(NamedTuple):
    idx: int
    name: str
    url: AbsoluteHttpURL


def _parse_segments(segments: Sequence[Segment | InitializationSection]) -> Generator[HLSSegment]:
    padding = max(5, len(str(len(segments))))
    for index, segment in enumerate(segments, 1):
        assert segment.uri
        yield HLSSegment(
            idx=index - 1,
            name=f"{index:0{padding}d}{constants.TempExt.HLS}",
            url=parse_url(segment.absolute_uri),
        )


def _create_media_segments(
    media_item: MediaItem,
    segments: Iterable[HLSSegment],
    download_folder: Path,
) -> Generator[MediaItem]:
    for segment in segments:
        # TODO: segments download should bypass the downloads slots limits.
        # They count as a single download

        seg_media_item = MediaItem(
            url=segment.url,
            domain=media_item.domain,
            download_folder=download_folder,
            filename=segment.name,
            db_path=media_item.db_path,
            referer=media_item.url,
            album_id=media_item.album_id,
            ext=media_item.ext,
            parents=media_item.parents,
            uploaded_at=media_item.uploaded_at,
            is_segment=True,
        )
        seg_media_item.headers = media_item.headers.copy()
        yield seg_media_item


def _segments(m3u8: M3U8) -> list[Segment | InitializationSection]:
    segments = m3u8.segment_map + m3u8.segments
    if not segments:
        msg = f"{m3u8.media_type} m3u8 manifest ({m3u8.base_uri}) has no valid segments"
        raise DownloadError(HTTPStatus.NO_CONTENT, msg)
    return segments


async def _download_m3u8(
    m3u8: M3U8,
    temp_dir: Path,
    media_item: MediaItem,
    download_fn: DownloadFn,
    sem: asyncio.BoundedSemaphore,
) -> Path:
    assert m3u8.media_type
    segments = _segments(m3u8)
    output = _prepare_output_path(m3u8, media_item.path)
    if await aio.is_file(output):
        return output

    async def download(seg_media_item: MediaItem) -> SegmentDownloadResult:
        return SegmentDownloadResult(seg_media_item, await download_fn(seg_media_item))

    m_segments = _create_media_segments(
        media_item,
        _parse_segments(segments),
        download_folder=temp_dir / m3u8.media_type,
    )

    logger.debug(f"Starting HLS download ({m3u8.media_type}, {len(segments):,} segments) for {media_item.real_url}")
    results = await _download_segments(m_segments, m3u8.total_segments, download, sem)
    await _merge_segments(tuple(result.item.path for result in results), output)
    return output


async def _download_segments(
    segments: Iterable[MediaItem],
    count: int,
    download: Callable[[MediaItem], Awaitable[SegmentDownloadResult]],
    sem: asyncio.BoundedSemaphore,
) -> list[SegmentDownloadResult]:
    results = await aio.map(
        download,
        segments,
        task_limit=sem,
    )

    n_successful = sum(1 for result in results if result.downloaded)
    if n_successful != count:
        msg = f"Download of some segments failed. Successful: {n_successful:,}/{count:,} "
        raise DownloadError("HLS Seg Error", msg)

    return results


async def _merge_segments(seg_paths: Sequence[Path], output: Path) -> None:
    if len(seg_paths) == 1:
        _ = await aio.move(seg_paths[0], output)
        return

    await ffmpeg.raw_concat(seg_paths, output)


def _prepare_output_path(m3u8: M3U8, output: Path) -> Path:
    real_ext = parse_url(m3u8.segments[0].absolute_uri).suffix
    if len(m3u8.segments) > 1:
        suffix = f".{m3u8.media_type}{real_ext}" if m3u8.media_type == "subtitle" else f".{m3u8.media_type}.ts"
    else:
        suffix = output.suffix + real_ext

    return output.with_suffix(suffix)


async def download(media_item: MediaItem, rendition: Rendition, download_fn: DownloadFn) -> Streams:
    """Download a rendition group"""
    temp_dir = media_item.path.with_suffix(constants.TempExt.HLS)

    sem = asyncio.BoundedSemaphore(CONCURRENT_SEGMENTS.get())

    async def download(m3u8: M3U8) -> Path:
        return await _download_m3u8(m3u8, temp_dir, media_item, download_fn, sem)

    async def download_subs() -> Path | None:
        if not rendition.subtitle:
            return None
        try:
            subs = await download(rendition.subtitle)
        except Exception:
            logger.exception(f"Unable to download subtitles for {media_item.url}, Skipping")
        else:
            logger.warning(
                f"Found subtitles for {media_item.url}, but CDL is currently unable to merge them. Subtitle were saved at '{subs}'"
            )
            return subs

    async def download_audio() -> Path | None:
        if rendition.audio:
            return await download(rendition.audio)

    async with asyncio.TaskGroup() as tg:
        # Keep this priority for the semaphore: subs > audio > video
        subs = tg.create_task(download_subs())
        audio = tg.create_task(download_audio())
        video = tg.create_task(download(rendition.video))

    try:
        await aio.rmdir(temp_dir)
    except OSError:
        pass

    return Streams(video.result(), audio.result(), subs.result())
