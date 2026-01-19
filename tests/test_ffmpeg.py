import pytest

from cyberdrop_dl.data_structures import AbsoluteHttpURL
from cyberdrop_dl.utils import ffmpeg

FFPROBE_IS_INSTALLED = bool(ffmpeg.get_ffprobe_version())

pytestmark = pytest.mark.skipif(not FFPROBE_IS_INSTALLED, reason="ffprobe is not installed")


async def test_ffprobe_video_url() -> None:
    output = await ffmpeg.probe(
        AbsoluteHttpURL("https://videos.pexels.com/video-files/29691053/12769314_360_640_60fps.mp4")
    )
    # assert output.audio
    # assert output.audio.codec == "aac"
    # assert output.audio.duration == 7.808
    # assert str(output.audio.duration) == "7.81"
    # assert output.audio.sample_rate == 48000

    assert output.video
    assert output.video.codec == "h264"
    assert output.video.bitrate == 4_014_556
    assert output.video.fps and round(output.video.fps) == 60.0
    assert output.video.width == 360
    assert output.video.height == 640

    tags = output.video.tags
    assert tags["language"] == "und"
    assert tags["handler_name"] == "Core Media Video"
    assert tags["encoder"] == "Lavc60.31.102 libx264"
