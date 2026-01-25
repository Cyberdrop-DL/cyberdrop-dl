import datetime

import pytest

from cyberdrop_dl.data_structures import AbsoluteHttpURL
from cyberdrop_dl.utils import ffmpeg

FFPROBE_IS_INSTALLED = bool(ffmpeg.get_ffprobe_version())

pytestmark = pytest.mark.skipif(not FFPROBE_IS_INSTALLED, reason="ffprobe is not installed")


async def test_ffprobe_video_url() -> None:
    output = await ffmpeg.probe(
        AbsoluteHttpURL("https://videos.pexels.com/video-files/29691053/12769314_360_640_60fps.mp4")
    )

    assert output.video
    assert output.video.duration == 10.5105
    assert str(output.video.duration) == "10.51"
    assert output.video.codec == "h264"
    assert output.video.bitrate == 4_014_556
    assert output.video.fps and round(output.video.fps) == 60.0
    assert output.video.width == 360
    assert output.video.height == 640

    assert output.format.bitrate == 4_019_301
    assert output.format.duration == 10.5105
    assert output.format.size == 5_280_609

    tags = output.video.tags
    assert tags["language"] == "und"
    assert tags["handler_name"] == "Core Media Video"
    assert tags["encoder"] == "Lavc60.31.102 libx264"


@pytest.mark.parametrize(
    "input, hours, minutes, seconds",
    [
        # numbers
        (42.5, 0, 0, 42.5),
        (123, 0, 0, 123),
        # minutes:seconds
        ("3:30", 0, 3, 30),
        ("10:07.25", 0, 10, 7.25),
        ("00:00:30.000000000", 0, 0, 30),
        # hours:minutes:seconds
        ("00:08:37.503", 0, 8, 37.503),
        ("1:23:45.6", 1, 23, 45.6),
        ("99:59:59.999", 99, 59, 59.999),
        # 60+ seconds
        ("0:0:120.5", 0, 2, 0.5),
    ],
)
def test_parse_duration(input: str, hours: float, minutes: float, seconds: float) -> None:
    output = ffmpeg._parse_duration(input)
    expected = datetime.timedelta(hours=hours, minutes=minutes, seconds=seconds).total_seconds()
    assert output == expected


@pytest.mark.parametrize(
    "input",
    ["0", "0:00", "00:00:00", None, "", -1, False, "Invalid"],
)
def test_parse_null_duration(input: str) -> None:
    output = ffmpeg._parse_duration(input)
    assert output is None
