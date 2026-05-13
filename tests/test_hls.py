from pathlib import Path

from m3u8.model import Segment

from cyberdrop_dl.downloader import hls
from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem


def test_parse_segments() -> None:
    segments = [Segment(uri="/m3u8/test", base_uri="https://example.com") for _ in range(8)]
    result = list(hls._parse_segments(segments))
    assert len(result) == 8
    first = result[0]
    assert type(first) is hls.HLSSegment
    assert first.idx == 0
    assert first.part is None
    assert first.url == AbsoluteHttpURL("https://example.com/m3u8/test")
    assert first.name == "00001.cdl_hls"
    last = result[-1]
    assert last.name == "00008.cdl_hls"


def test_create_media_segments() -> None:
    folder = Path("downloads")
    item = MediaItem(
        url=AbsoluteHttpURL("https://example.com/m3u8/test"),
        filename="a filename.mp4",
        domain="example.com",
        referer=AbsoluteHttpURL("https://example.com/m3u8/test"),
        ext=".mp4",
        db_path="/m3u8/test",
        download_folder=folder,
    )
    segment = hls.HLSSegment(
        idx=22,
        part="image.jpg",
        name="00023.cdl_hls",
        url=AbsoluteHttpURL("https://example.com/m3u8/test/segments001.ts"),
    )
    result = list(hls._create_media_segments(item, [segment], folder / "video_hls"))
    assert len(result) == 1
    seg_item = result[0]
    assert seg_item.url == segment.url
    assert seg_item.download_folder == folder / "video_hls"
    assert seg_item.filename == segment.name
    assert seg_item.original_filename == segment.name
    assert seg_item.is_segment is True
    assert seg_item.headers == item.headers
    assert seg_item.headers is not item.headers
    assert seg_item.ext == item.ext
