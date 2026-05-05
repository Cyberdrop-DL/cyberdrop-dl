from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import itertools
import random
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Final, final

from rich.jupyter import JupyterMixin
from rich.markup import escape
from rich.measure import Measurement
from rich.progress import (
    BarColumn,
    DownloadColumn,
    SpinnerColumn,
    Task,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
    filesize,
)
from rich.table import Column
from rich.text import Text
from typing_extensions import override

from cyberdrop_dl.progress import DictProgress, ProgressHook, create_test_live, strip_markup, truncate_float
from cyberdrop_dl.progress.overflow import OverFlowPanel

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from rich.console import Console, ConsoleOptions, RenderableType, RenderResult

_current_hls_task: ContextVar[TaskID] = ContextVar("_current_hls_task")
_HLS_TASK_FIELD_NAME: Final = "HLS"


@dataclasses.dataclass(slots=True)
class AutoWidth(JupyterMixin):
    """Expand (if possible) or truncate a renderable to a desired width ratio of the screen"""

    renderable: RenderableType
    ratio: float
    min_cells: int = 10
    min_cells_after: int = 70

    def _desired_width(self, console_width: int) -> int:
        return max(self.min_cells, int(min((console_width * self.ratio), (console_width - self.min_cells_after))))

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        my_options = options.update_width(min(self._desired_width(console.width), options.max_width))
        yield from console.render(self.renderable, my_options)

    def __rich_measure__(self, console: Console, options: ConsoleOptions) -> Measurement:
        my_options = options.update_width(self._desired_width(console.width))
        return Measurement.get(console, my_options, self.renderable)


class AutoWidthTextColumn(TextColumn):
    @override
    def render(self, task: Task) -> AutoWidth:  # pyright: ignore[reportIncompatibleMethodOverride]
        text = super().render(task)
        return AutoWidth(text, ratio=0.6)


class AutoTransferSpeedColumn(TransferSpeedColumn):
    @override
    def render(self, task: Task) -> Text:
        real_task: Task = task.fields.get(_HLS_TASK_FIELD_NAME, task)
        return super().render(real_task)


class AutoDownloadColumn(DownloadColumn):
    """Shows `<x>/<y> MBs` for files and `<downloaded_bytes> MBs (<x>/<y> segments)` for HLS downloads"""

    @override
    def render(self, task: Task) -> Text:
        hls_task: Task | None = task.fields.get(_HLS_TASK_FIELD_NAME)
        if hls_task is None:
            return super().render(task)

        downloaded_bytes = self._format_bytes(int(hls_task.completed))
        completed_segs = int(task.completed)
        total_segs = "?" if task.total is None else f"{int(task.total):,}"
        total_width = len(str(total_segs))
        download_status = f"{downloaded_bytes} ({completed_segs:>{total_width},}/{total_segs})"
        return Text(download_status, style="progress.download", justify="right")

    def _format_bytes(self, n_bytes: int) -> str:
        multiplier, unit = self._select_bytes_units(n_bytes)
        precision = 0 if multiplier == 1 else 1
        normalized_n_bytes = n_bytes / multiplier
        n_bytes_str = f"{normalized_n_bytes:,.{precision}f}"
        return f"{n_bytes_str} {unit}"

    def _select_bytes_units(self, size: int) -> tuple[int, str]:
        if self.binary_units:
            return filesize.pick_unit_and_suffix(
                size,
                ["bytes", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB"],
                1024,
            )

        return filesize.pick_unit_and_suffix(
            size,
            ["bytes", "kB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"],
            1000,
        )


@final
class DownloadsPanel(OverFlowPanel):
    unit: ClassVar[str] = "file"

    @property
    def bytes_downloaded(self) -> int:
        return self._total_bytes

    def __init__(self, max_rows: int = 6) -> None:
        super().__init__(
            SpinnerColumn("dots3"),
            AutoWidthTextColumn(
                "[progress.description]{task.description}",
                table_column=Column(justify="left", no_wrap=True),
            ),
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>6.1f}%",
            "•",
            AutoDownloadColumn(table_column=Column(justify="right", no_wrap=True)),
            "•",
            AutoTransferSpeedColumn(table_column=Column(justify="right", no_wrap=True, min_width=11)),
            "•",
            TimeRemainingColumn(
                compact=True,
                elapsed_when_finished=True,
                table_column=Column(justify="right", no_wrap=True),
            ),
            max_rows=max_rows,
        )
        self._hls_progress: Final[DictProgress] = DictProgress("")
        self._total_bytes = 0

    @contextlib.contextmanager
    def download_hls(
        self,
        filename: str,
        /,
        domain: str,
        segments: float,
    ) -> Generator[None]:
        # For HLS downloads, we use 2 different tasks. One on a hidden progress to track the downloaded bytes
        # and one on the user facing progress to track the number of downloaded segments (with a known total)
        # We create both at the same time and smuggle the bytes task as a field of the segments task
        # to make all info available to the main progress for rendering

        task_id = self._hls_progress.add_task("", total=None, visible=False)
        filename = str(filename).rsplit("/", 1)[-1]
        desc = escape((f"({domain.upper()}) {filename}").encode().decode("ascii", errors="ignore"))
        segments_task = self._add_task(desc, segments)
        bytes_task = self._hls_progress[task_id]
        self._progress.update(segments_task.id, HLS=bytes_task)
        token = _current_hls_task.set(segments_task.id)
        try:
            yield
        finally:
            self._remove_task(segments_task)
            self._hls_progress.remove_task(task_id)
            _current_hls_task.reset(token)

    def download_file(
        self,
        description: object,
        /,
        domain: str,
        total: float | None,
    ) -> ProgressHook:
        filename = str(description).rsplit("/", 1)[-1]
        desc = escape((f"({domain.upper()}) {filename}").encode().decode("ascii", errors="ignore"))
        task = self._add_task(desc, total)

        def advance(amount: int = 1) -> None:
            self._total_bytes += amount
            self._progress.advance(task.id, amount)

        def on_exit() -> None:
            self._remove_task(task)

        def get_speed() -> float:
            return task.finished_speed or task.speed or 0

        return ProgressHook(advance, get_speed, on_exit)

    def download_hls_seg(self) -> ProgressHook:
        segments_task_id = _current_hls_task.get()
        hls_task: Task = self._progress[segments_task_id].fields[_HLS_TASK_FIELD_NAME]

        def advance(amount: int) -> None:
            self._total_bytes += amount
            self._hls_progress.advance(hls_task.id, amount)

        def on_exit() -> None:
            self._progress.advance(segments_task_id, 1)

        def get_speed() -> float:
            return hls_task.finished_speed or hls_task.speed or 0

        return ProgressHook(advance, get_speed, on_exit)

    def __json__(self) -> tuple[dict[str, Any], ...]:
        return tuple(_dump_task(tasks) for tasks in self._progress.tasks)

    async def simulate(self) -> None:

        async def download(hook: ProgressHook, size: int) -> None:
            total = 0
            with hook:
                while total < size:
                    chunk = min(random.randint(1, int(1e7)), size - total)
                    hook.advance(chunk)
                    total += chunk
                    await asyncio.sleep(0.1)

        async def download_file(filename: str) -> None:
            size = random.randint(int(1e2), int(1e9))
            hook = self.download_file(filename, "example.com", size)
            await download(hook, size)

        async def download_hls(filename: str) -> None:
            n_segments = random.randint(1, 1_200)
            segments_sem = asyncio.BoundedSemaphore(20)

            async def download_segment() -> None:
                size = random.randint(int(1e2), int(1e5))
                hook = self.download_hls_seg()
                try:
                    await download(hook, size)
                finally:
                    segments_sem.release()

            with self.download_hls(filename, "example.com", n_segments):
                async with asyncio.TaskGroup() as tg:
                    for _ in range(n_segments):
                        await segments_sem.acquire()
                        tg.create_task(download_segment())

        files = random.choices(
            [
                str(f.with_suffix(random.choice([".py", ".exe", ".jpg", ".mp4", ".zip"])))
                for f in Path(__file__).parent.parent.rglob("*")
            ],
            k=random.randint(80, 200),
        )
        async with asyncio.TaskGroup() as tg:

            def download_files(files: Iterable[str]) -> None:
                tg.create_task(download_file("file_X_with_a_very_long_name_and_?_#.mp4"))
                for file in files:
                    fn = random.choice([download_hls, download_file])
                    tg.create_task(fn(file))

            batches = 4
            batch_size = len(files) // batches
            iter_files = iter(files)
            for _ in range(batches):
                download_files(itertools.islice(iter_files, batch_size))
                # The overflow number should go up every 2 seconds
                await asyncio.sleep(2)


def _dump_task(task: Task) -> dict[str, Any]:
    real_task: Task = task.fields.get(_HLS_TASK_FIELD_NAME, task)
    return {
        "speed": truncate_float(real_task.finished_speed or real_task.speed),
        "size": task.total,
        "completed": task.completed,
        "hls": _HLS_TASK_FIELD_NAME in task.fields,
        "bytes_downloaded": real_task.completed,
        "description": strip_markup(task.description),
        "eta": task.time_remaining,
        "visible": task.visible,
    }


if __name__ == "__main__":
    panel = DownloadsPanel()
    import itertools

    panel.get_queue = itertools.count(1).__next__
    with create_test_live(panel):
        asyncio.run(panel.simulate())
