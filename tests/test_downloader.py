from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from cyberdrop_dl.clients.downloads import _get_content_length, filter_by_duration
from cyberdrop_dl.downloader.http import Downloader
from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem

if TYPE_CHECKING:
    from cyberdrop_dl.manager import Manager


def test_downloader_creation(manager: Manager) -> None:
    downloader = Downloader(manager)
    assert type(downloader.slots) is int
    assert downloader.slots > 0


def test_changing_downloader_limit(manager: Manager) -> None:
    downloader = Downloader(manager)
    assert downloader.slots == 5
    assert downloader._semaphore._value == 5
    downloader.slots = 3
    assert downloader.slots == 3
    assert downloader._semaphore._value == 3


async def test_changing_downloader_limit_after_usage_raises_error(manager: Manager) -> None:
    downloader = Downloader(manager)
    await downloader._semaphore.acquire()
    with pytest.raises(RuntimeError, match="Downloader is already in use"):
        downloader.slots = 3


async def test_probe_duration_is_skipped_on_default_config(manager: Manager) -> None:
    item = MediaItem(
        url=AbsoluteHttpURL("https://www.example.com"),
        domain="example.com",
        download_folder=Path(),
        filename="filename",
        db_path="db_path",
        referer=AbsoluteHttpURL("https://www.example.com"),
        album_id=None,
        ext=".mp4",
        original_filename="filename.mp4",
        uploaded_at=None,
    )
    with mock.patch("cyberdrop_dl.ffmpeg.probe") as fn:
        result = await filter_by_duration(item, manager.config)
        assert not result

    assert fn.self.call_count == 0


def test_missing_content_lenght() -> None:
    assert _get_content_length({"Content-Length": "200"}) == 200
    assert _get_content_length({}) == 0
