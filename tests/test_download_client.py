from pathlib import Path

import pytest
from multidict import CIMultiDict

from cyberdrop_dl.clients.downloads import DownloadClient, _check_content_type, _get_content_type, resolve_download_dir
from cyberdrop_dl.config import Config
from cyberdrop_dl.constants import USE_RETRY_PATH
from cyberdrop_dl.exceptions import InvalidContentTypeError
from cyberdrop_dl.manager import Manager
from cyberdrop_dl.utils import enter_context


@pytest.mark.parametrize(
    "limit",
    [
        (5_000_000,),
        (500_000_000,),
    ],
)
def test_chunk_size_is_never_greater_that_speed_limit(manager: Manager, limit: int) -> None:
    max_expected = 1024 * 1024 * 10
    limit = manager.config.downloads.speed_limit
    assert limit == 0
    client = DownloadClient(manager)
    assert client.chunk_size != limit
    assert client.chunk_size == max_expected

    manager.config.downloads.speed_limit = limit
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


class TestResolveDownloadDir:
    @pytest.fixture
    @staticmethod
    def config(tmp_path: Path) -> Config:
        download_folder = tmp_path / "downloads"
        return Config(download_folder=download_folder)

    def test_returns_download_folder_when_subfolders_enabled(self, config: Config) -> None:
        download_folder = config.download_folder / "folder1" / "folder2"
        config.subfolders.create = True
        result = resolve_download_dir(download_folder, config)
        assert result == download_folder

    def test_keeps_only_first_subfolder(self, config: Config) -> None:
        download_folder = config.download_folder / "folder1" / "folder2" / "folder3"
        config.subfolders.create = False
        result = resolve_download_dir(download_folder, config)
        assert result == config.download_folder / "folder1"

    def test_returns_download_root_when_no_subfolders(self, config: Config) -> None:
        download_folder = config.download_folder
        result = resolve_download_dir(download_folder, config)
        assert result == config.download_folder

    def test_returns_download_folder_when_retry_path_enabled(self, config: Config) -> None:
        download_folder = Path("/not_relative/to/download/dir")

        with enter_context(USE_RETRY_PATH, True):
            result = resolve_download_dir(download_folder, config)

        assert result == download_folder

    def test_returns_download_folder_when_subfolders_create_is_enabled(self, config: Config) -> None:
        download_folder = Path("/not_relative/to/download/dir")
        result = resolve_download_dir(download_folder, config)
        assert result == download_folder

    def test_raises_error_on_non_relative_path_if_subfolder_create_is_false(self, config: Config) -> None:
        download_folder = Path("/not_relative/to/download/dir")
        config.subfolders.create = False
        with pytest.raises(ValueError, match="is not in the subpath of"):
            resolve_download_dir(download_folder, config)
