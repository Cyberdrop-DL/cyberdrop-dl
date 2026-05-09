from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cyberdrop_dl import csv_logs
from cyberdrop_dl.csv_logs import CSVFiles, CSVLogsManager
from cyberdrop_dl.progress import ProgressHook, chain_hooks


def _make_manager(tmp_path: Path, *, progress: bool = False, scrape: bool = False) -> CSVLogsManager:
    main_log = tmp_path / "downloader.log"
    files = CSVFiles(
        main_log=main_log,
        last_post_log=tmp_path / "last.csv",
        unsupported_urls_log=tmp_path / "unsupported.csv",
        download_error_log=tmp_path / "download_errors.csv",
        scrape_error_log=tmp_path / "scrape_errors.csv",
        progress_events_file=main_log.with_suffix(".progress.jsonl") if progress else None,
        scrape_events_file=main_log.with_suffix(".scrape.jsonl") if scrape else None,
    )
    return CSVLogsManager(files)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines() if line]


def test_csv_files_iter_skips_none(tmp_path: Path) -> None:
    main = tmp_path / "downloader.log"
    files = CSVFiles(
        main_log=main,
        last_post_log=tmp_path / "a.csv",
        unsupported_urls_log=tmp_path / "b.csv",
        download_error_log=tmp_path / "c.csv",
        scrape_error_log=tmp_path / "d.csv",
        progress_events_file=None,
        scrape_events_file=None,
    )
    assert all(isinstance(p, Path) for p in files)
    assert main.with_suffix(".results.jsonl") in list(files)


def test_chain_hooks_fans_advance_and_done() -> None:
    advances_a: list[int] = []
    advances_b: list[int] = []
    done_calls: list[str] = []

    a = ProgressHook(advances_a.append, lambda: 12.5, lambda: done_calls.append("a"))
    b = ProgressHook(advances_b.append, lambda: 99.0, lambda: done_calls.append("b"))

    chained = chain_hooks(a, b)
    chained.advance(7)
    chained.advance(3)
    assert advances_a == [7, 3]
    assert advances_b == [7, 3]
    assert chained.get_speed() == 12.5

    with chained:
        pass
    assert done_calls == ["a", "b"]


def test_chain_hooks_requires_at_least_one() -> None:
    with pytest.raises(ValueError):
        _ = chain_hooks()


async def test_progress_event_noop_when_disabled(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path, progress=False)
    async with mgr.task_group:
        mgr.write_progress_event({"event": "start", "url": "x"})
    assert not (tmp_path / "downloader.progress.jsonl").exists()


async def test_progress_event_writes_when_enabled(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path, progress=True)
    async with mgr.task_group:
        mgr.write_progress_event({"event": "start", "url": "https://x/foo", "total": 10})
        mgr.write_progress_event({"event": "finish", "url": "https://x/foo", "bytes": 10, "ok": True})

    rows = _read_jsonl(tmp_path / "downloader.progress.jsonl")
    assert [r["event"] for r in rows] == ["start", "finish"]
    assert rows[0]["url"] == "https://x/foo"
    assert rows[1]["bytes"] == 10


async def test_scrape_event_noop_when_disabled(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path, scrape=False)
    async with mgr.task_group:
        mgr.write_scrape_event({"event": "stats", "queued": 1})
    assert not (tmp_path / "downloader.scrape.jsonl").exists()


async def test_make_progress_writer_emits_start_and_finish(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path, progress=True)
    async with mgr.task_group:
        hook = mgr.make_progress_writer(
            url="https://x/foo.mp4",
            filename="foo.mp4",
            total=1000,
            interval=0.0,
            min_bytes=0,
        )
        with hook:
            hook.advance(500)
            hook.advance(500)

    rows = _read_jsonl(tmp_path / "downloader.progress.jsonl")
    events = [r["event"] for r in rows]
    assert events[0] == "start"
    assert events[-1] == "finish"
    assert "chunk" in events
    assert rows[0]["total"] == 1000
    assert rows[0]["filename"] == "foo.mp4"
    assert rows[-1]["bytes"] == 1000
    assert rows[-1]["ok"] is True


async def test_make_progress_writer_throttles_chunks(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path, progress=True)
    async with mgr.task_group:
        hook = mgr.make_progress_writer(
            url="https://x/foo.mp4",
            filename="foo.mp4",
            total=1_000_000,
            interval=10.0,
            min_bytes=10_000_000,
        )
        with hook:
            for _ in range(50):
                hook.advance(1000)

    rows = _read_jsonl(tmp_path / "downloader.progress.jsonl")
    chunks = [r for r in rows if r["event"] == "chunk"]
    assert chunks == []
    assert rows[0]["event"] == "start"
    assert rows[-1]["event"] == "finish"
    assert rows[-1]["bytes"] == 50_000


async def test_progress_writer_chunk_bytes_are_cumulative(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path, progress=True)
    async with mgr.task_group:
        hook = mgr.make_progress_writer(
            url="https://x/foo.mp4",
            filename="foo.mp4",
            total=None,
            interval=0.0,
            min_bytes=0,
        )
        with hook:
            hook.advance(100)
            hook.advance(150)
            hook.advance(50)

    rows = _read_jsonl(tmp_path / "downloader.progress.jsonl")
    chunks = [r["bytes"] for r in rows if r["event"] == "chunk"]
    assert chunks == sorted(chunks)
    assert chunks[-1] == 300


async def test_progress_writer_emits_nothing_when_never_used(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path, progress=True)
    async with mgr.task_group:
        _ = mgr.make_progress_writer(
            url="https://x/foo.mp4",
            filename="foo.mp4",
            total=1000,
            interval=0.0,
            min_bytes=0,
        )
    assert not (tmp_path / "downloader.progress.jsonl").exists()


async def test_progress_writer_done_without_advance_pairs_start_and_finish(tmp_path: Path) -> None:
    mgr = _make_manager(tmp_path, progress=True)
    async with mgr.task_group:
        hook = mgr.make_progress_writer(
            url="https://x/foo.mp4",
            filename="foo.mp4",
            total=1000,
            interval=0.0,
            min_bytes=0,
        )
        with hook:
            pass

    rows = _read_jsonl(tmp_path / "downloader.progress.jsonl")
    assert [r["event"] for r in rows] == ["start", "finish"]
    assert rows[-1]["bytes"] == 0


def test_ensure_parent_creates_dirs(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c.jsonl"
    csv_logs._ensure_parent(nested)
    assert nested.parent.is_dir()


async def test_progress_event_creates_parent_dir(tmp_path: Path) -> None:
    main = tmp_path / "nested" / "logs" / "downloader.log"
    files = CSVFiles(
        main_log=main,
        last_post_log=tmp_path / "a.csv",
        unsupported_urls_log=tmp_path / "b.csv",
        download_error_log=tmp_path / "c.csv",
        scrape_error_log=tmp_path / "d.csv",
        progress_events_file=main.with_suffix(".progress.jsonl"),
    )
    mgr = CSVLogsManager(files)
    async with mgr.task_group:
        mgr.write_progress_event({"event": "start", "url": "x"})

    expected = main.with_suffix(".progress.jsonl")
    assert expected.exists()
    assert _read_jsonl(expected)[0]["event"] == "start"
