from pathlib import Path
from unittest import mock

from cyberdrop_dl.clients.downloads import filter_by_duration
from cyberdrop_dl.manager import Manager
from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem


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
