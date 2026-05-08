from cyberdrop_dl.clients.download_client import DownloadClient
from cyberdrop_dl.config import Config
from cyberdrop_dl.manager import Manager


def test_chunk_size_is_never_greater_that_speed_limit() -> None:
    manager = Manager()
    limit = manager.config.global_settings.rate_limiting_options.download_speed_limit
    assert limit == 0
    client = DownloadClient(manager)
    assert client.chunk_size != limit
    assert client.chunk_size == 1024 * 1024 * 10

    manager = Manager(config=Config.parse_args(["--download-speed-limit", "5MB"]))
    limit = manager.config.global_settings.rate_limiting_options.download_speed_limit
    assert limit == 5_000_000
    client = DownloadClient(manager)
    assert client.chunk_size == limit
