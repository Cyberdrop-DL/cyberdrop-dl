import pytest

from cyberdrop_dl.data_structures import AbsoluteHttpURL
from cyberdrop_dl.utils import ffmpeg

FFPROBE_IS_INSTALLED = bool(ffmpeg.get_ffprobe_version())

pytestmark = pytest.mark.skipif(not FFPROBE_IS_INSTALLED, reason="ffprobe is not installed")


async def test_ffprobe_video_url() -> None:
    output = await ffmpeg.probe(AbsoluteHttpURL("https://data.saint2.cr/data/LM54NzGj8PO.mp4"))
    assert output.audio
    assert output.audio.codec == "aac"
    assert output.audio.duration == 7.808
    assert str(output.audio.duration) == "7.81"
    assert output.audio.sample_rate == 48000

    assert output.video
    assert output.video.codec == "h264"
    assert output.video.bitrate and output.video.bitrate > 785000
    assert output.video.fps == 30.0
    assert output.video.width == 480
    assert output.video.height == 854

    tags = output.video.tags
    assert tags["language"] == "und"
    assert tags["handler_name"] == "VideoHandler"
    assert tags["encoder"] == "AVC Coding"
