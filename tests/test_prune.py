# ruff: noqa: ASYNC240
from __future__ import annotations

import contextlib
import os
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from cyberdrop_dl import aio, program_ui
from cyberdrop_dl.__main__ import run_cdl
from cyberdrop_dl.database import Database
from cyberdrop_dl.database.hash import _path_exists, _path_exists_inner
from cyberdrop_dl.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from cyberdrop_dl.manager import Manager

_HASH = "a5aec63d0fef8660b00570f23be727e9"
_REFERER = AbsoluteHttpURL("https://example.com/file.txt")


@contextlib.contextmanager
def _stat_raises(target: Path, error: OSError) -> Generator[None]:
    """Make `os.stat` fail for a single path, leaving every other path alone."""
    real_stat = os.stat

    def fake_stat(path, *args, **kwargs):
        if str(path) == str(target):
            raise error
        return real_stat(path, *args, **kwargs)

    with patch("os.stat", fake_stat):
        yield


async def _add_file(database: Database, file: Path) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(file.name)
    await database.hash.insert_or_update_hash_db(_HASH, "md5", file, file.name, _REFERER)


async def _count(database: Database, table: str) -> int:
    async with database.reader() as db_conn:
        cursor = await db_conn.execute(f"SELECT COUNT(*) AS count FROM {table};")  # noqa: S608
        row = await cursor.fetchone()
        assert row is not None
        return row["count"]


async def _filenames(database: Database, table: str) -> set[str]:
    async with database.reader() as db_conn:
        rows = await db_conn.execute_fetchall(f"SELECT download_filename FROM {table};")  # noqa: S608
        return {row["download_filename"] for row in rows}


@pytest.fixture
async def database(running_manager: Manager) -> Database:
    return running_manager.database


@pytest.fixture
def txt_file(tmp_cwd: Path) -> Path:
    file = tmp_cwd / "text_file.txt"
    file.write_text("12345")
    return file


@pytest.fixture(autouse=True)
def _clear_path_cache() -> Generator[None]:
    _path_exists_inner.cache_clear()
    yield
    _path_exists_inner.cache_clear()


class TestPruneMissingFiles:
    async def test_removes_rows_of_deleted_files(self, database: Database, tmp_cwd: Path) -> None:
        kept, gone = tmp_cwd / "kept.txt", tmp_cwd / "gone.txt"
        await _add_file(database, kept)
        await _add_file(database, gone)
        gone.unlink()

        stats = await database.hash.prune_missing_files()

        assert stats.hash_rows == 1
        assert stats.file_rows == 1
        assert await _filenames(database, "files") == {"kept.txt"}
        assert await _filenames(database, "hash") == {"kept.txt"}

    async def test_keeps_everything_when_no_file_is_missing(self, database: Database, tmp_cwd: Path) -> None:
        await _add_file(database, tmp_cwd / "kept.txt")

        stats = await database.hash.prune_missing_files()

        assert stats.hash_rows == 0
        assert stats.file_rows == 0
        assert await _count(database, "files") == 1
        assert await _count(database, "hash") == 1

    async def test_removes_every_hash_algo_of_a_missing_file(self, database: Database, tmp_cwd: Path) -> None:
        gone = tmp_cwd / "gone.txt"
        await _add_file(database, gone)
        await database.hash.insert_or_update_hashes(_HASH, "sha256", gone)
        assert await _count(database, "hash") == 2
        gone.unlink()

        stats = await database.hash.prune_missing_files()

        assert stats.hash_rows == 2
        assert stats.file_rows == 1
        assert await _count(database, "hash") == 0

    async def test_removes_orphan_hash_row_with_no_files_row(self, database: Database, tmp_cwd: Path) -> None:
        orphan = tmp_cwd / "orphan.txt"
        await database.hash.insert_or_update_hashes(_HASH, "md5", orphan)
        assert await _count(database, "files") == 0

        stats = await database.hash.prune_missing_files()

        assert stats.hash_rows == 1
        assert stats.file_rows == 0
        assert await _count(database, "hash") == 0

    async def test_dry_run_reports_counts_without_deleting(self, database: Database, tmp_cwd: Path) -> None:
        gone = tmp_cwd / "gone.txt"
        await _add_file(database, tmp_cwd / "kept.txt")
        await _add_file(database, gone)
        gone.unlink()

        stats = await database.hash.prune_missing_files(dry_run=True)

        assert stats.dry_run is True
        assert stats.hash_rows == 1
        assert stats.file_rows == 1
        assert await _count(database, "files") == 2
        assert await _count(database, "hash") == 2

    async def test_keeps_rows_whose_path_cannot_be_checked(self, database: Database, tmp_cwd: Path) -> None:
        unreadable = tmp_cwd / "unreadable.txt"
        await _add_file(database, unreadable)
        unreadable.unlink()

        with _stat_raises(unreadable, PermissionError(13, "Permission denied")):
            stats = await database.hash.prune_missing_files()

        assert stats.hash_rows == 0
        assert stats.file_rows == 0
        assert await _count(database, "files") == 1
        assert await _count(database, "hash") == 1

    async def test_clears_the_path_cache_when_done(self, database: Database, tmp_cwd: Path) -> None:
        await _add_file(database, tmp_cwd / "kept.txt")
        _path_exists(str(tmp_cwd), "primed.txt")
        assert _path_exists_inner.cache_info().currsize == 1

        await database.hash.prune_missing_files()

        assert _path_exists_inner.cache_info().currsize == 0


class TestPathExists:
    def test_reports_an_existing_file(self, txt_file: Path) -> None:
        assert _path_exists(str(txt_file.parent), txt_file.name) is True

    def test_reports_a_deleted_file(self, txt_file: Path) -> None:
        txt_file.unlink()
        assert _path_exists(str(txt_file.parent), txt_file.name) is False

    def test_reports_a_path_it_cannot_read_as_still_there(self, txt_file: Path) -> None:
        with _stat_raises(txt_file, PermissionError(13, "Permission denied")):
            assert _path_exists(str(txt_file.parent), txt_file.name) is True

    def test_looks_a_repeated_path_up_only_once(self, txt_file: Path) -> None:
        _path_exists(str(txt_file.parent), txt_file.name)
        _path_exists(str(txt_file.parent), txt_file.name)

        assert _path_exists_inner.cache_info().hits == 1


class TestPruneCommand:
    @staticmethod
    def _seed(db_file: Path, *files: Path) -> None:
        async def seed() -> None:
            async with Database(db_file) as database:
                for file in files:
                    await _add_file(database, file)

        aio.run(seed())

    @staticmethod
    def _read(db_file: Path, table: str) -> set[str]:
        async def read() -> set[str]:
            async with Database(db_file) as database:
                return await _filenames(database, table)

        return aio.run(read())

    def test_removes_rows_of_deleted_files(self, capsys: pytest.CaptureFixture[str], tmp_cwd: Path) -> None:
        db_file, kept, gone = tmp_cwd / "test.db", tmp_cwd / "kept.txt", tmp_cwd / "gone.txt"
        self._seed(db_file, kept, gone)
        gone.unlink()

        exit_code = run_cdl(["database", "prune", "hashes", "--database-file", str(db_file)])

        assert exit_code == 0
        assert "Deleted: 1 hash entries" in capsys.readouterr().out
        assert self._read(db_file, "files") == {"kept.txt"}
        assert self._read(db_file, "hash") == {"kept.txt"}

    def test_dry_run_keeps_every_row(self, tmp_cwd: Path) -> None:
        db_file, kept, gone = tmp_cwd / "test.db", tmp_cwd / "kept.txt", tmp_cwd / "gone.txt"
        self._seed(db_file, kept, gone)
        gone.unlink()

        exit_code = run_cdl(["database", "prune", "hashes", "--database-file", str(db_file), "--dry-run"])

        assert exit_code == 0
        assert self._read(db_file, "files") == {"kept.txt", "gone.txt"}
        assert self._read(db_file, "hash") == {"kept.txt", "gone.txt"}


class TestPruneMenuEntry:
    @staticmethod
    def _seed(manager: Manager, *files: Path) -> None:
        async def seed() -> None:
            async with manager.database:
                for file in files:
                    await _add_file(manager.database, file)

        aio.run(seed())

    @staticmethod
    def _read(manager: Manager, table: str) -> set[str]:
        async def read() -> set[str]:
            async with manager.database:
                return await _filenames(manager.database, table)

        return aio.run(read())

    @pytest.fixture(autouse=True)
    def _no_prompts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(program_ui, "enter_to_continue", lambda: None)

    def test_prunes_after_explicit_confirmation(self, manager: Manager, tmp_cwd: Path) -> None:
        gone = tmp_cwd / "gone.txt"
        self._seed(manager, tmp_cwd / "kept.txt", gone)
        gone.unlink()

        with patch.object(program_ui, "ask_confirmation", return_value=True):
            program_ui._prune_hashes(manager)

        assert self._read(manager, "files") == {"kept.txt"}
        assert self._read(manager, "hash") == {"kept.txt"}

    def test_keeps_every_row_when_confirmation_is_declined(self, manager: Manager, tmp_cwd: Path) -> None:
        gone = tmp_cwd / "gone.txt"
        self._seed(manager, tmp_cwd / "kept.txt", gone)
        gone.unlink()

        with patch.object(program_ui, "ask_confirmation", return_value=False):
            program_ui._prune_hashes(manager)

        assert self._read(manager, "files") == {"kept.txt", "gone.txt"}
        assert self._read(manager, "hash") == {"kept.txt", "gone.txt"}
