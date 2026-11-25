from __future__ import annotations

import contextlib
import errno
import logging
import sqlite3
from collections.abc import Callable, Generator
from pathlib import Path

from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeRemainingColumn

from cyberdrop_dl.database.conn import stdlib_connect
from cyberdrop_dl.filepath import sanitize_filename
from cyberdrop_dl.utils import dates

logger = logging.getLogger(__name__)

type _ProgressHook = Callable[[int, int, int], object]


@contextlib.contextmanager
def _progress_tracker() -> Generator[_ProgressHook]:
    with Progress(
        TextColumn("[bold cyan]Backing up database..."),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        TextColumn("•"),
        TimeRemainingColumn(compact=True, elapsed_when_finished=True),
        transient=True,
    ) as progress:
        task = progress.add_task("Backing up database...", total=100)

        def hook(_: object, remaining: int, total: int) -> None:
            progress.update(
                task,
                completed=total - remaining,
                total=total,
            )

        yield hook


def _normalize_paths(source: Path, /, destination: Path | None = None) -> tuple[Path, Path]:
    source = source.resolve(strict=True)

    if destination is None:
        now = sanitize_filename(str(dates.now()))
        destination = source.with_suffix(f".backup_{now}{source.suffix}")

    else:
        destination = destination.resolve().absolute()

        if source == destination:
            raise OSError(errno.EINVAL, "Source and target are the same file")

        if destination.exists():
            raise FileExistsError(errno.EEXIST, f"The destination already exists: '{destination}'")

        destination.parent.mkdir(parents=True, exist_ok=True)

    return source, destination


def backup_database(source: Path, /, destination: Path | None = None) -> Path:
    source, destination = _normalize_paths(source, destination)
    _backup(source, destination, show_progress=True)
    return destination


def _backup(source: Path, destination: Path, *, show_progress: bool = True) -> None:
    logger.info("Backing up '%s'", source)
    try:
        with (
            contextlib.closing(stdlib_connect(source, "source")) as src,
            contextlib.closing(stdlib_connect(destination, "destination")) as dst,
            _progress_tracker() if show_progress else contextlib.nullcontext() as progress_hook,
        ):
            src.backup(
                dst,
                pages=1_000 if show_progress else -1,
                progress=progress_hook,
                sleep=0.05,
            )
    except Exception as exc:
        logger.error(f"Backup failed: {exc}", extra={"color": "red"})
        raise

    logger.info("Backup completed successfully!", extra={"color": "green"})
    logger.info("Destination: '%s'", destination)


def _fail_wal_merge(db_path: Path) -> RuntimeError:
    exc = RuntimeError(f"Unable to merge WAL files into database '{db_path.name}'")
    exc.add_note("Make sure to close all connections to the database from any other process")
    return exc


def merge_journal_files(db_path: Path) -> None:
    """Merge all journal files (WAL mode) into the main database file

    This only works if there are no other connections to the database"""
    db_path = db_path.resolve(strict=True)
    try:
        _merge_journal_files(db_path)
    except (sqlite3.Error, OSError) as e:
        raise _fail_wal_merge(db_path) from e


def _merge_journal_files(db_path: Path) -> None:
    with contextlib.closing(stdlib_connect(db_path, "WAL merge")) as conn:
        # these pragmas are no-op if WAL is disabled so it is safe to use even for a v9 db
        # 1. merge as much as possible without waiting for any other connection to finish
        cursor = conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
        # 2. now force a full merge, waiting up to 5s for all other connections to close (if any)
        cursor.execute("PRAGMA busy_timeout = 5000;")
        with contextlib.closing(cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")):
            row = cursor.fetchone()
            assert row is not None

        if row["busy"]:
            raise _fail_wal_merge(db_path)

        if row["log"] != row["checkpointed"]:
            exc = _fail_wal_merge(db_path)
            exc.add_note(f"Not all pages where checkpointed: {dict(row)}")
            raise exc

    for file in _journal_files(db_path):
        _delete_journal_if_empty(db_path, file)


def _delete_journal_if_empty(db_path: Path, journal_file: Path) -> None:
    try:
        stat = journal_file.stat()
    except FileNotFoundError:
        return
    except OSError as e:
        raise _fail_wal_merge(db_path) from e

    # Only delete 0 byte files after the merge
    if stat.st_size > 0:
        raise _fail_wal_merge(db_path)

    journal_file.unlink()


def _journal_files(db_path: Path) -> list[Path]:
    return [db_path.with_name(f"{db_path.name}-{suffix}") for suffix in ("journal", "wal", "shm")]


def delete_database(db_path: Path) -> None:
    "Force delete database and all of its journal files (WAL mode)"
    db_path.unlink()
    for file in _journal_files(db_path):
        file.unlink(missing_ok=True)


if __name__ == "__main__":
    import sys

    from cyberdrop_dl import tracebacks
    from cyberdrop_dl.logs import setup_console_logging

    tracebacks.install_exception_hook()

    with setup_console_logging():
        database = Path(sys.argv[1])
        backup_database(database)
