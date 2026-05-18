from __future__ import annotations

import dataclasses
import time
from pathlib import Path
from typing import TYPE_CHECKING, Literal, final

from rich.align import Align
from rich.console import Group
from rich.markup import escape
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn

from cyberdrop_dl.progress import LiveUI, ProgressHook

if TYPE_CHECKING:
    from collections.abc import Generator


@dataclasses.dataclass(slots=True)
class HashingStats:
    xxh128: int = 0
    md5: int = 0
    sha256: int = 0

    new_hashed: int = 0
    prev_hashed: int = 0

    @property
    def files(self) -> int:
        return self.new_hashed + self.prev_hashed

    @property
    def computed_hashes(self) -> int:
        return sum((self.xxh128, self.md5, self.sha256))


@final
class HashingUI(LiveUI):
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
        self._stats: HashingStats = HashingStats()
        self._tasks_map: dict[str, TaskID] = dict(self._init_tasks())
        self._total: int = 0
        self._panel = Panel(
            Group(
                "[green]Base dir: [blue]" + escape(f"{base_dir}"),
                self._progress,
                Align.center("----------"),
                self._files,
            ),
            title="Hashing",
            border_style="green",
            padding=(1, 1),
        )

    def _init_tasks(self) -> Generator[tuple[str, TaskID]]:
        for algo in ("xxh128", "md5", "sha256"):
            desc = "[cyan]Hashed " + escape(f"[{algo}]")
            yield algo, self._progress.add_task(desc, total=None)

        yield "prev_hashed", self._progress.add_task("[yellow]Previously Hashed", total=None)

    @property
    def stats(self) -> HashingStats:
        return self._stats

    def __rich__(self) -> Panel:
        current_total = self._stats.files
        if current_total != self._total:
            for name, task_id in self._tasks_map.items():
                self._progress.update(task_id, total=current_total, completed=getattr(self._stats, name))
            self._total = current_total

        self._panel.subtitle = f"Files:  [white]{current_total:,}[/white], New Computed Hashes: [white]{self._stats.computed_hashes:,}[/white]"
        return self._panel

    def new_file(self, file: Path):
        task_id = self._files.add_task(
            "[blue]" + escape(str(file.relative_to(self._base_dir))),
            total=None,
        )

        return ProgressHook(lambda _: None, lambda: 0, lambda: self._files.remove_task(task_id))

    def add_completed(self, hash_type: Literal["xxh128", "md5", "sha256"]) -> None:
        setattr(self._stats, hash_type, getattr(self._stats, hash_type) + 1)
        if hash_type == "xxh128":
            self.stats.new_hashed += 1


if __name__ == "__main__":
    panel = HashingUI(folder := Path("/folder1/cdl_downloads"))

    with panel(transient=False), panel.new_file(folder / "file.txt"):
        time.sleep(3)
        panel.stats.md5 += 1
        panel.stats.prev_hashed += 1
        panel.stats.new_hashed += 1
        with panel.new_file(folder / "subfolder/file2.txt"), panel.new_file(folder / "subfolder/file3.txt"):
            time.sleep(1)
            panel.stats.sha256 += 5
            panel.stats.new_hashed += 5
            time.sleep(1)
        panel.stats.xxh128 += 15
        time.sleep(3)
