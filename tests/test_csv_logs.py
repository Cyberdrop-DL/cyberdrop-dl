import datetime
from pathlib import Path

import pytest

from cyberdrop_dl.csv_logs import _prepare_resp_file, _write_to_csv
from cyberdrop_dl.url_objects import AbsoluteHttpURL

now = datetime.datetime(2026, 5, 8, tzinfo=datetime.UTC)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://static.scdn.st/e2f8a4c6-3d7b-4e19-9a5c-8b1d6f0e3a7c/thumbs/f7e8625e-b50b-42c3-93da-d74bce716c41-md8f1c79417cd16004-zU4LIum1.png",
            "/https-static.scdn.st-e2f8a4c6-3d7b-4e19-9a5c-8b1d6f0e3a7c-thumbs-f7e8625e-b50b-42c3-93da-d74bce716c41-md8f1c79417cd16004-zU4LIum1.png_20260508_000000.html",
        ),
        (
            "https://cloud.mail.ru/public/d1LR/hMBXG2mFo",
            "/https-cloud.mail.ru-public-d1LR-hMBXG2mFo_20260508_000000.html",
        ),
        (
            "https://www.tokyomotion.net/video/5884366/%E3%83%A1%E3%82%B9%E7%89%9B%E3%81%8A%E3%81%BB%E3%82%A4%E3%82%AD%E3%83%81%E3%82%AF%E3%83%8B%E3%83%BC",
            "/https-www.tokyomotion.net-video-5884366-%E3%83%A1%E3%82%B9%E7%89%9B%E3%81%8A%E3%81%BB%E3%82%A4%E3%82%AD%E3%83%81%E3%82%AF%E3%83%8B%E3%83%BC_20260508_000000.html",
        ),
    ],
)
def test_prepare_resp_filename(url: str, expected: str) -> None:
    result = _prepare_resp_file(Path("/"), AbsoluteHttpURL(url), now)
    assert result.as_posix().count("/") == 1
    assert result.as_posix() == expected


class TestWriteToCsv:
    @pytest.fixture
    def row(self) -> dict[str, object]:
        return {"url": "https://example.com", "origin": "URLs.txt"}

    def test_parent_dirs_are_created_when_write_headers_true(self, tmp_path: Path, row: dict[str, object]) -> None:
        file = tmp_path / "subfolder" / "errors.csv"
        _write_to_csv(file, row, write_headers=True)
        assert file.exists()

    def test_parent_dirs_are_not_created_when_write_headers_false(self, tmp_path: Path, row: dict[str, object]) -> None:
        file = tmp_path / "subfolder" / "errors.csv"
        with pytest.raises(FileNotFoundError):
            _write_to_csv(file, row, write_headers=False)

    def test_file_is_always_appended_to(self, tmp_path: Path, row: dict[str, object]) -> None:
        file = tmp_path / "subfolder" / "errors.csv"
        file.parent.mkdir()
        header = "<<TEST_HEADER>>"
        file.write_text(header + "\n")
        _write_to_csv(file, row, write_headers=False)

        lines = file.read_text().splitlines()
        assert len(lines) == 2
        assert lines[0] == header
        assert lines[1] == '"https://example.com","URLs.txt"'

    def test_write_headers_true(self, tmp_path: Path, row: dict[str, object]) -> None:
        file = tmp_path / "subfolder" / "errors.csv"
        _write_to_csv(file, row, write_headers=True)
        assert file.read_text().splitlines()[0] == '"url","origin"'

    def test_write_headers_false(self, tmp_path: Path, row: dict[str, object]) -> None:
        file = tmp_path / "errors.csv"
        _write_to_csv(file, row, write_headers=False)
        assert file.read_text().splitlines()[0] == '"https://example.com","URLs.txt"'

    def test_row_w_various_data_types(self, tmp_path: Path) -> None:
        file = tmp_path / "subfolder" / "errors.csv"

        class CustomType:
            def __init__(self, a: str) -> None:
                self.a: str = a

        _write_to_csv(
            file,
            row={
                "string": "hello",
                "integer": 42,
                "float": 3.14,
                "boolean": True,
                "none_value": None,
                "list_value": [1, 2, 3],
                "custom_type": CustomType("test"),
            },
            write_headers=True,
        )
