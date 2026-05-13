from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, NamedTuple

from cyberdrop_dl import aio, constants, ffmpeg
from cyberdrop_dl.exceptions import (
    DownloadError,
)
from cyberdrop_dl.url_objects import HlsSegment, MediaItem
from cyberdrop_dl.utils import parse_url

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Generator, Iterable
    from pathlib import Path

    from cyberdrop_dl.utils.m3u8 import M3U8

logger = logging.getLogger(__name__)


class SegmentDownloadResult(NamedTuple):
    item: MediaItem
    downloaded: bool


def _create_segments(media_item: MediaItem, m3u8: M3U8, download_folder: Path) -> Generator[MediaItem]:
    for segment in _parse_segments(m3u8):
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
        yield seg_media_item


def _parse_segments(m3u8: M3U8) -> Generator[HlsSegment]:
    padding = max(5, len(str(len(m3u8.segments))))
    for index, segment in enumerate(m3u8.segments, 1):
        assert segment.uri
        name = f"{index:0{padding}d}{constants.TempExt.HLS}"
        yield HlsSegment(segment.title, name, parse_url(segment.absolute_uri))


async def download_m3u8(
    m3u8: M3U8,
    temp_dir: Path,
    media_item: MediaItem,
    download_fn: Callable[[MediaItem], Awaitable[bool]],
):
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

    tasks_results = await _download_segments(_create_segments(media_item, m3u8, download_folder), download_fn)

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


async def _download_segments(
    segments: Iterable[MediaItem],
    download_fn: Callable[[MediaItem], Awaitable[bool]],
) -> list[SegmentDownloadResult]:
    async def download(seg_media_item: MediaItem):
        return SegmentDownloadResult(seg_media_item, await download_fn(seg_media_item))

    return await aio.map(download, segments, task_limit=10)
