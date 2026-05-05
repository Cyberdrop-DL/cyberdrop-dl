from __future__ import annotations

import asyncio
import dataclasses
import time
from typing import TYPE_CHECKING, Any, final

from rich.panel import Panel
from rich.progress import BarColumn, Progress, TaskID, TextColumn

from cyberdrop_dl.progress import create_test_live

if TYPE_CHECKING:
    from collections.abc import Generator


@dataclasses.dataclass(slots=True)
class FileStats:
    completed: int = 0
    previously_completed: int = 0
    skipped: int = 0
    failed: int = 0
    queued: int = 0

    @property
    def total(self) -> int:
        return sum(dataclasses.astuple(self))


@final
class FileStatsPanel:
    """Class that keeps track of completed, skipped and failed files."""

    def __init__(self) -> None:
        columns = (
            "[progress.description]{task.description}",
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>6.2f}%",
            "•",
            TextColumn("{task.completed:,}", justify="right"),
        )

        self._progress: Progress = Progress(*columns, expand=True)
        self._stats = FileStats()
        self._total: int = 0
        self._tasks_map: dict[str, TaskID] = dict(self._init_tasks())
        self._simple: Progress = Progress(*columns)
        self._tasks_map["simple"] = self._simple.add_task("Completed", total=1)
        self._panel: Panel = Panel(
            self._progress,
            title="Files",
            border_style="green",
            padding=(1, 1),
        )

    def _init_tasks(self) -> Generator[tuple[str, TaskID]]:
        for name, color, desc in (
            ("completed", "green", "Completed"),
            ("previously_completed", "yellow", "Previously downloaded"),
            ("skipped", "yellow", "Skipped by config"),
            ("queued", "cyan", "Queued"),
            ("failed", "red", "Failed"),
        ):
            yield name, self._progress.add_task(f"[{color}]{desc}", total=1)

    def __rich__(self) -> Panel:
        self._refresh()
        return self._panel

    @property
    def simple(self) -> Progress:
        self._refresh()
        return self._simple

    def _refresh(self) -> None:
        current_total = self._stats.total
        if current_total != self._total:
            for name, task_id in self._tasks_map.items():
                if name == "simple":
                    self._simple.update(task_id, total=current_total, completed=current_total - self._stats.queued)
                else:
                    self._progress.update(task_id, total=current_total, completed=getattr(self._stats, name))
            self._total = current_total

        self._panel.subtitle = f"Total: [white]{current_total:,}"

    def __json__(self) -> dict[str, Any]:
        return dataclasses.asdict(self._stats)

    @property
    def stats(self) -> FileStats:
        return self._stats

    async def simulate(self) -> None:
        await asyncio.sleep(3)
        self.stats.completed += 1
        await asyncio.sleep(1)
        self.stats.queued += 5
        await asyncio.sleep(1)
        self.stats.failed += 15
        await asyncio.sleep(1)
        self.stats.previously_completed += 1
        await asyncio.sleep(1)
        self.stats.skipped += 10
        await asyncio.sleep(3)


if __name__ == "__main__":
    panel = FileStatsPanel()
    with create_test_live(panel):
        asyncio.run(panel.simulate())

    with panel.simple:
        time.sleep(3)
