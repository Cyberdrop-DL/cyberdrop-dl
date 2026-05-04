# ruff: noqa: ASYNC240
from pathlib import Path
from unittest.mock import patch

import pytest

from cyberdrop_dl.dedupe import _delete_file


@pytest.fixture
def txt_file(tmp_path: Path) -> Path:
    file = tmp_path / "dummy.txt"
    file.write_text("hello")
    return file


class TestDeleteFile:
    async def test_delete_to_trash_success(self, txt_file: Path) -> None:
        assert txt_file.exists()
        ok = await _delete_file(txt_file, to_trash=True)
        assert ok is True
        assert not txt_file.exists()

    async def test_delete_permanent_success(self, txt_file: Path) -> None:
        assert txt_file.exists()
        ok = await _delete_file(txt_file, to_trash=False)
        assert ok is True
        assert not txt_file.exists()

    async def test_file_already_gone(self, tmp_path: Path) -> None:
        ghost = tmp_path / "gone.txt"
        assert not ghost.exists()
        ok = await _delete_file(ghost, to_trash=True)
        assert ok is False

    async def test_send2trash_raises_wrapped_filenotfound(self) -> None:
        with patch("send2trash.send2trash", side_effect=OSError("File not found")):
            ok = await _delete_file(Path("/no/such/file"), to_trash=True)
            assert ok is False

    async def test_send2trash_raises_other_oserror(self) -> None:
        with patch("send2trash.send2trash", side_effect=OSError("Permission denied")):
            with pytest.raises(OSError, match="Permission denied"):
                await _delete_file(Path("/foo"), to_trash=True)

    async def test_aio_unlink_raises_other_oserror(self, txt_file: Path) -> None:
        with patch("cyberdrop_dl.aio.unlink", side_effect=OSError("Read-only fs")):
            with pytest.raises(OSError, match="Read-only fs"):
                await _delete_file(txt_file, to_trash=False)
