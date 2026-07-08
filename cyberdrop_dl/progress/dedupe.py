from __future__ import annotations

import dataclasses
import time
from pathlib import Path
from typing import TYPE_CHECKING, final

from rich.align import Align
from rich.console import Group
from rich.markup import escape
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn

from cyberdrop_dl.progress import LiveUI, ProgressHook

if TYPE_CHECKING:
    from collections.abc import Generator


@dataclasses.dataclass(slots=True)
class DedupeStats:
    deleted: int = 0
    total: int = 0


@final
class DedupeUI(LiveUI):
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._progress = Progress(
            "[progress.description]{task.description}",
            BarColumn(bar_width=None),
            TextColumn("{task.completed:,}", justify="right"),
        )
        self._files = Progress(
            SpinnerColumn("dots3"),
            "[progress.description]{task.description}",
        )

        self._stats: DedupeStats = DedupeStats()
        self._total: int = 0
        self._tasks_map: dict[str, TaskID] = dict(self._init_tasks())
        self._panel = Panel(
            Group(
                "[green]Base dir: [blue]" + escape(f"{base_dir}"),
                self._progress,
                Align.center("----------"),
                self._files,
            ),
            title="Dedupe",
            border_style="green",
            padding=(1, 1),
        )

    @property
    def stats(self) -> DedupeStats:
        return self._stats

    def __rich__(self) -> Panel:
        current_total = self._stats.total
        if current_total != self._total:
            for name, task_id in self._tasks_map.items():
                self._progress.update(task_id, total=current_total, completed=getattr(self._stats, name))
            self._total = current_total

        self._panel.subtitle = f"Total: [white]{current_total:,}"
        return self._panel

    def _init_tasks(self) -> Generator[tuple[str, TaskID]]:
        yield "deleted", self._progress.add_task("[yellow]Deleted", total=None)

    def new_file(self, file: Path) -> ProgressHook:
        task_id = self._files.add_task(
            "[blue]" + escape(str(file.relative_to(self._base_dir))),
            total=None,
        )
        self._stats.total += 1

        return ProgressHook(lambda _: None, lambda: 0, lambda: self._files.remove_task(task_id))


if __name__ == "__main__":
    panel = DedupeUI(folder := Path("/folder1/cdl_downloads"))

    with panel(transient=False), panel.new_file(folder / "file.txt"):
        time.sleep(3)
        panel.stats.deleted += 1
        with panel.new_file(folder / "subfolder/file2.txt"), panel.new_file(folder / "subfolder/file3.txt"):
            time.sleep(1)
            panel.stats.total += 5
            time.sleep(1)
        panel.stats.deleted += 15
        time.sleep(3)
