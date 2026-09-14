# ruff: noqa: ASYNC240
import dataclasses
import sqlite3
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from cyberdrop_dl.config import Config
from cyberdrop_dl.csv_logs import CSVFiles
from cyberdrop_dl.dedupe import Czkawka, _delete_file, _filter_db_matches
from cyberdrop_dl.hasher import FileHashes
from cyberdrop_dl.manager import Manager

_HASH = "a5aec63d0fef8660b00570f23be727e9"


@pytest.fixture
def txt_file(tmp_path: Path) -> Path:
    file = tmp_path / "text_file.txt"
    file.write_text("12345")
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
        with (
            patch("send2trash.send2trash", side_effect=OSError("Permission denied")),
            pytest.raises(OSError, match="Permission denied"),
        ):
            await _delete_file(Path("/foo"), to_trash=True)

    async def test_aio_unlink_raises_other_oserror(self, txt_file: Path) -> None:
        with (
            patch("cyberdrop_dl.aio.unlink", side_effect=OSError("Read-only fs")),
            pytest.raises(OSError, match="Read-only fs"),
        ):
            await _delete_file(txt_file, to_trash=False)


class TestFilterDbMatches:
    @staticmethod
    def _row(folder: Path | str, download_filename: str) -> sqlite3.Row:
        return cast("sqlite3.Row", {"folder": folder, "download_filename": download_filename})  # pyright: ignore[reportInvalidCast]

    def test_filter_db_matches_should_pair_every_duplicate_with_the_first_row(self, tmp_path: Path) -> None:
        rows = [
            self._row(tmp_path, "skip_me.txt"),
            self._row(tmp_path, "do not skip me.txt"),
            self._row(tmp_path, "do not skip me 2.txt"),
        ]
        original = tmp_path / "skip_me.txt"
        found = list(_filter_db_matches(rows, tmp_path))
        assert found == [
            (original, tmp_path / "do not skip me.txt"),
            (original, tmp_path / "do not skip me 2.txt"),
        ]

    def test_filter_db_matches_should_skip_non_relative_paths(self, tmp_path: Path) -> None:
        rows = [
            self._row(tmp_path, "skip_me.txt"),
            self._row(tmp_path, "do not skip me.txt"),
            self._row("/another/dir", "skip me 2.txt"),
            self._row(tmp_path, "do not skip me 2.txt"),
        ]
        original = tmp_path / "skip_me.txt"
        found = list(_filter_db_matches(rows, tmp_path))
        assert found == [
            (original, tmp_path / "do not skip me.txt"),
            (original, tmp_path / "do not skip me 2.txt"),
        ]

    def test_filter_db_matches_should_report_originals_outside_base_dir(self, tmp_path: Path) -> None:
        rows = [
            self._row("/another/dir", "original.txt"),
            self._row(tmp_path, "dupe.txt"),
        ]
        found = list(_filter_db_matches(rows, tmp_path))
        assert found == [(Path("/another/dir/original.txt"), tmp_path / "dupe.txt")]

    def test_filtering_a_single_row(self, tmp_path: Path) -> None:
        assert list(_filter_db_matches([self._row(tmp_path, "alone.txt")], tmp_path)) == []

    def test_filtering_no_rows(self) -> None:
        assert list(_filter_db_matches([], Path("/a/dir"))) == []


@dataclasses.dataclass(frozen=True, slots=True)
class _DedupeCase:
    deduper: Czkawka
    file_hashes: FileHashes
    original: Path
    duplicate: Path

    @property
    def csv_file(self) -> Path:
        return self.deduper.csv_files.dedupe

    async def run(self) -> None:
        await self.deduper.run(self.file_hashes)


async def _seed_duplicates(manager: Manager, base_dir: Path, *names: str) -> tuple[list[Path], FileHashes]:
    """Registers files that all share the same hash in the database. The first one is the original"""

    files: list[Path] = []
    for name in names:
        file = base_dir / name
        file.parent.mkdir(parents=True, exist_ok=True)
        _ = file.write_text("same content")
        await manager.database.hash.insert_or_update_hash_db(_HASH, "xxh128", file, None, None)
        files.append(file)

    return files, {_HASH: {files[0].stat().st_size: set(files)}}


def _deduper(manager: Manager, base_dir: Path, log_folder: Path) -> Czkawka:
    config = Config()
    config.logs.resolve_filenames(log_folder)
    return Czkawka(
        base_dir=base_dir,
        database=manager.database,
        use_trash_bin=False,
        csv_files=CSVFiles.from_config(config),
    )


class TestDedupeRun:
    @pytest.fixture
    async def case(self, running_manager: Manager, tmp_path: Path) -> _DedupeCase:
        base_dir = tmp_path / "downloads"
        files, file_hashes = await _seed_duplicates(running_manager, base_dir, "original.jpg", "sub/duplicate.jpg")
        deduper = _deduper(running_manager, base_dir, tmp_path / "logs")
        return _DedupeCase(deduper, file_hashes, files[0], files[1])

    async def test_deletes_the_duplicate_and_keeps_the_original(self, case: _DedupeCase) -> None:
        await case.run()
        assert case.original.exists()
        assert not case.duplicate.exists()

    async def test_logs_the_path_of_the_original(self, case: _DedupeCase, logs: pytest.LogCaptureFixture) -> None:
        await case.run()
        assert f"Removed new download '{case.duplicate}'" in logs.text
        assert f"duplicate of '{case.original}'" in logs.text

    async def test_logs_the_start_and_the_end_of_the_dedupe(
        self, case: _DedupeCase, logs: pytest.LogCaptureFixture
    ) -> None:
        await case.run()
        assert "Starting dedupe" in logs.text
        assert "Dedupe finished. Deleted 1 of 1 duplicates found" in logs.text

    async def test_writes_the_csv_log(self, case: _DedupeCase) -> None:
        await case.run()
        assert case.csv_file.read_text("utf8").splitlines() == [
            '"duplicate","original","hash"',
            f'"{case.duplicate}","{case.original}","xxh128:{_HASH}"',
        ]

    async def test_writes_one_csv_row_per_duplicate_under_a_single_header(
        self, running_manager: Manager, tmp_path: Path
    ) -> None:
        base_dir = tmp_path / "downloads"
        files, file_hashes = await _seed_duplicates(running_manager, base_dir, "original.jpg", "one.jpg", "two.jpg")
        deduper = _deduper(running_manager, base_dir, tmp_path / "logs")
        await deduper.run(file_hashes)

        original, *duplicates = files
        header, *rows = deduper.csv_files.dedupe.read_text("utf8").splitlines()
        assert header == '"duplicate","original","hash"'
        assert sorted(rows) == sorted(f'"{dupe}","{original}","xxh128:{_HASH}"' for dupe in duplicates)

    async def test_no_csv_log_when_nothing_was_deleted(self, case: _DedupeCase) -> None:
        await case.deduper.run({})
        assert not case.csv_file.exists()

    def test_from_manager_uses_the_csv_file_from_the_config(self, manager: Manager) -> None:
        assert Czkawka.from_manager(manager).csv_files.dedupe == manager.config.logs.files.dedupe
