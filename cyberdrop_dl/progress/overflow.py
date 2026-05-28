from __future__ import annotations

import dataclasses
from collections import deque
from typing import TYPE_CHECKING, Any, ClassVar, Final, final

from rich.console import Group
from rich.markup import escape
from rich.panel import Panel
from rich.progress import Task, TaskID

from cyberdrop_dl.progress import Color, DictProgress

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from rich.progress import ProgressColumn, Task, TaskID


def _plural(ammount: int, unit: str) -> str:
    return f"{unit}{'s' if ammount > 1 else ''}"


@final
@dataclasses.dataclass(slots=True)
class OverFlow:
    unit: str
    count: int = 0
    queued: int = 0

    def __bool__(self) -> bool:
        return self.count > 0 or self.queued > 0

    def __rich__(self) -> str:
        if self:
            return str(self)
        return ""

    def __str__(self) -> str:
        overflow = f"[{Color.PLUM}]... and {self.count:,} other {_plural(self.count, self.unit)}"
        if self.count > 0 and self.queued > 0:
            return overflow + f"[{Color.YELLOW}] ({self.queued:,} queued)"

        if self.queued > 0:
            return f"[{Color.YELLOW}] ... and {self.queued:,} {_plural(self.queued, self.unit)} queued"

        if self.count > 0:
            return overflow

        return ""


class OverFlowPanel:
    unit: ClassVar[str]

    def __init__(
        self,
        *columns: ProgressColumn | str,
        max_rows: int,
        expand: bool = True,
        get_queue: Callable[[], int] = lambda: 0,
    ) -> None:
        self.max_rows: int = max_rows
        self._progress: Final[DictProgress] = DictProgress(*columns, expand=expand)
        self._overflow: Final[OverFlow] = OverFlow(self.unit)
        self._invisible_rows: Final[deque[TaskID]] = deque()
        self._visible_rows: int = 0
        self.get_queue: Callable[[], int] = get_queue
        self._panel: Final[Panel] = Panel(
            Group(self._progress, self._overflow),
            title=type(self).__name__.removesuffix("Panel"),
            border_style="green",
            padding=(1, 1),
        )

    @final
    def __rich__(self) -> Panel:
        self._overflow.count = len(self._progress) - self._visible_rows
        self._overflow.queued = self.get_queue()
        return self._panel

    @final
    def _add_task(
        self,
        description: object,
        total: float | None = None,
        /,
        *,
        completed: int = 0,
        fields: Mapping[str, Any] | None = None,
    ) -> Task:
        visible = self._visible_rows < self.max_rows
        task_id = self._progress.add_task(
            escape(str(description)),
            total=total,
            visible=visible,
            completed=completed,
            **(fields or {}),
        )
        if visible:
            self._visible_rows += 1
        else:
            self._invisible_rows.append(task_id)

        return self._progress[task_id]

    @final
    def _remove_task(self, task: Task) -> None:
        was_visible = task.visible
        self._progress.remove_task(task.id)

        if was_visible:
            self._visible_rows -= 1
            try:
                self._push_one_invisible()
            except IndexError:
                pass

    @final
    def _push_one_invisible(self) -> None:
        while True:
            task_id = self._invisible_rows.popleft()
            try:
                self._progress.update(task_id, visible=True)
            except KeyError:
                continue
            else:
                self._visible_rows += 1
                break
