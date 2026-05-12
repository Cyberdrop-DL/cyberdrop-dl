import pytest
from multidict import CIMultiDict

from cyberdrop_dl.clients.downloads import DownloadClient, _check_content_type, _get_content_type
from cyberdrop_dl.exceptions import InvalidContentTypeError
from cyberdrop_dl.manager import Manager


@pytest.mark.parametrize(
    "limit",
    [
        (5_000_000,),
        (500_000_000,),
    ],
)
def test_chunk_size_is_never_greater_that_speed_limit(manager: Manager, limit: int) -> None:
    max_expected = 1024 * 1024 * 10
    limit = manager.config.global_settings.rate_limiting_options.download_speed_limit
    assert limit == 0
    client = DownloadClient(manager)
    assert client.chunk_size != limit
    assert client.chunk_size == max_expected

    manager.config.global_settings.rate_limiting_options.download_speed_limit = limit
    client = DownloadClient(manager)
    assert client.chunk_size == min(limit or max_expected, max_expected)


def test_get_content_type() -> None:
    def get(value: str) -> str:
        content_type = _get_content_type(CIMultiDict({"content-type": value}))
        assert content_type
        return content_type

    assert get("text/vnd.trolltech.linguist") == "video/MP2T"
    assert get("text/HTML") == "text/HTML"
    assert get("application/json") == "application/json"


def test_check_content_type() -> None:
    _check_content_type("text/html", ".txt")

    with pytest.raises(InvalidContentTypeError, match="Received 'text/html', was expecting binary payload"):
        _check_content_type("text/html", ".mp4")


def test_get_content_type_missing_headers() -> None:
    assert _get_content_type({}) is None
