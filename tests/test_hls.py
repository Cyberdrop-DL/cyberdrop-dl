from pathlib import Path

from m3u8.model import Segment

from cyberdrop_dl.downloader import hls
from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem
from cyberdrop_dl.utils.m3u8 import M3U8

VARIANT_M3U8_CONTENT = """
#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:10
#EXT-X-MEDIA-SEQUENCE:0

#EXTINF:10.000,
media-segment-00001.ts
#EXTINF:10.000,
media-segment-00002.ts
#EXTINF:8.500,
media-segment-00003.ts
#EXT-X-ENDLIST
"""

VARIANT_M3U8_CONTENT_SUBS = """
#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:10
#EXT-X-MEDIA-SEQUENCE:0

#EXTINF:10.000,
media-segment-00001.vtt
#EXTINF:10.000,
media-segment-00002.ts
#EXTINF:8.500,
media-segment-00003.ts
#EXT-X-ENDLIST
"""


def test_parse_segments() -> None:
    segments = [Segment(uri="/m3u8/test", base_uri="https://example.com") for _ in range(8)]
    result = list(hls._create_segments(segments, len(segments)))
    assert len(result) == 8
    first = result[0]
    assert type(first) is hls.HLSSegment
    assert first.idx == 0
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
        name="00023.cdl_hls",
        url=AbsoluteHttpURL("https://example.com/m3u8/test/segments001.ts"),
    )
    seg_item = hls._create_media_segment(item, segment, folder / "video_hls")
    assert seg_item.url == segment.url
    assert seg_item.download_folder == folder / "video_hls"
    assert seg_item.filename == segment.name
    assert seg_item.original_filename == segment.name
    assert seg_item.is_segment is True
    assert seg_item.headers == item.headers
    assert seg_item.headers is not item.headers
    assert seg_item.ext == item.ext


def test_prepare_output_path(tmp_path: Path) -> None:
    base_uri = AbsoluteHttpURL("https://www.example.com")
    m3u8 = M3U8(content=VARIANT_M3U8_CONTENT, media_type="video", base_uri=base_uri)
    output = tmp_path / "download" / "m3u8.mp4"
    file = hls._prepare_output_path(m3u8, output)
    assert file == tmp_path / "download" / "m3u8.video.ts"

    m3u8 = M3U8(content=VARIANT_M3U8_CONTENT_SUBS, media_type="subtitle", base_uri=base_uri)
    output = tmp_path / "download" / "m3u8.txt"
    file = hls._prepare_output_path(m3u8, output)
    assert file == tmp_path / "download" / "m3u8.subtitle.vtt"


def test_init_segments_should_be_include() -> None:
    content = """
    #EXTM3U
    #EXT-X-VERSION:6
    #EXT-X-PLAYLIST-TYPE:VOD
    #EXT-X-MEDIA-SEQUENCE:0
    #EXT-X-TARGETDURATION:5
    #EXT-X-MAP:URI="../../ac555a6ea0431c298d53d486a2cc1059/video/1080/init.mp4"
    #EXT-X-INDEPENDENT-SEGMENTS
    #EXTINF:4.00000,
    ../../ac555a6ea0431c298d53d486a2cc1059/video/1080/seg_1.mp4
    #EXTINF:4.00000,
    ../../ac555a6ea0431c298d53d486a2cc1059/video/1080/seg_2.mp4
    #EXTINF:4.00000,
    ../../ac555a6ea0431c298d53d486a2cc1059/video/1080/seg_3.mp4
    #EXTINF:4.00000,
    ../../ac555a6ea0431c298d53d486a2cc1059/video/1080/seg_4.mp4
    #EXTINF:2,
    ../../ac555a6ea0431c298d53d486a2cc1059/video/1080/seg_260.mp4
    #EXT-X-ENDLIST
    """
    m3u8 = M3U8(content)
    assert len(m3u8.segment_map) == 1
    assert len(m3u8.segments) == 5
    hls._check_segments(m3u8)
    assert m3u8.total_segments == 6


def _playlist(*urls: str) -> M3U8:
    return M3U8("#EXTM3U\n" + "".join(f"#EXTINF:10,\n{url}\n" for url in urls) + "#EXT-X-ENDLIST\n")


def test_playlist_id_ignores_query() -> None:
    first = _playlist("https://cdn.example.com/seg-1.ts?hash=abc", "https://cdn.example.com/seg-2.ts?hash=abc")
    second = _playlist("https://cdn.example.com/seg-1.ts?hash=xyz", "https://cdn.example.com/seg-2.ts?hash=xyz")
    assert hls._playlist_id(first) == hls._playlist_id(second)


def test_playlist_id_changes_with_segments() -> None:
    ts = _playlist("https://cdn.example.com/seg-1.ts", "https://cdn.example.com/seg-2.ts")
    fmp4 = _playlist("https://cdn.example.com/init.mp4", "https://cdn.example.com/seg-1.m4s")
    assert hls._playlist_id(ts) != hls._playlist_id(fmp4)


async def test_segments_of_the_same_playlist_are_kept(tmp_path: Path) -> None:
    folder = tmp_path / "video"
    await hls._discard_stale_segments(folder, "playlist-a")
    (folder / "00001.cdl_hls").write_bytes(b"segment")
    await hls._discard_stale_segments(folder, "playlist-a")
    assert (folder / "00001.cdl_hls").read_bytes() == b"segment"


async def test_segments_of_another_playlist_are_discarded(tmp_path: Path) -> None:
    folder = tmp_path / "video"
    await hls._discard_stale_segments(folder, "playlist-a")
    (folder / "00001.cdl_hls").write_bytes(b"segment")
    await hls._discard_stale_segments(folder, "playlist-b")
    assert not (folder / "00001.cdl_hls").exists()


async def test_segments_of_an_unknown_playlist_are_discarded(tmp_path: Path) -> None:
    folder = tmp_path / "video"
    folder.mkdir()
    (folder / "00001.cdl_hls").write_bytes(b"segment")
    await hls._discard_stale_segments(folder, "playlist-a")
    assert not (folder / "00001.cdl_hls").exists()


async def test_only_partial_files_are_discarded(tmp_path: Path) -> None:
    folder = tmp_path / "video"
    folder.mkdir()
    (folder / "00001.cdl_hls").write_bytes(b"segment")
    (folder / "notes.txt").write_text("not ours")
    await hls._discard_stale_segments(folder, "playlist-a")
    assert not (folder / "00001.cdl_hls").exists()
    assert (folder / "notes.txt").read_text() == "not ours"
