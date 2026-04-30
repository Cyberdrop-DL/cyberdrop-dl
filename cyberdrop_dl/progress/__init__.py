from __future__ import annotations

import contextlib
import dataclasses
import sys
from abc import ABC, abstractmethod
from contextvars import ContextVar
from typing import TYPE_CHECKING, Self

from rich.live import Live
from rich.markup import escape
from rich.progress import Progress, Task, TaskID
from rich.text import Text

from cyberdrop_dl.logs import disable_console_logging

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable
    from pathlib import Path

    from rich.console import RenderableType

REFRESH_RATE: ContextVar[float] = ContextVar("REFRESH_RATE", default=10.0)
TUI_DISABLED: ContextVar[bool] = ContextVar("TUI_DISABLED", default=False)


def create_test_live(renderable: RenderableType, transient: bool = False) -> Live:
    return Live(
        auto_refresh=True,
        refresh_per_second=20,
        transient=transient,
        get_renderable=lambda: renderable,
    )


def hyperlink(file_path: Path, text: str | None = None) -> Text:
    text = escape(text or str(file_path))
    return Text.from_markup(f"[link={file_path.as_uri()}]{text}[/link]", style="blue")


class DictProgress(Progress):
    """A progress with a dict like interface to access tasks"""

    def __getitem__(self, task_id: TaskID) -> Task:
        with self._lock:
            return self._tasks[task_id]

    def __len__(self) -> int:
        with self._lock:
            return len(self._tasks)

    def sort_tasks(self, sort_fn: Callable[[Iterable[Task]], list[Task]]) -> None:
        with self._lock:
            sorted_tasks = sort_fn(self._tasks.values())
            self._tasks.clear()
            self._tasks.update((task.id, task) for task in sorted_tasks)


@dataclasses.dataclass(slots=True)
class ProgressHook:
    advance: Callable[[int], None]
    get_speed: Callable[[], float]
    done: Callable[[], None]

    _done: bool = dataclasses.field(init=False, default=False)

    @property
    def speed(self) -> float:
        return self.get_speed()

    def __enter__(self) -> Self:
        if self._done:
            raise RuntimeError
        return self

    def __exit__(self, *_) -> None:
        if self._done:
            raise RuntimeError
        self.done()
        self._done = True


class LiveUI(ABC):
    @property
    def disabled(self) -> bool:
        return TUI_DISABLED.get()

    @disabled.setter
    def disabled(self, value: bool) -> None:
        _ = TUI_DISABLED.set(value)

    @abstractmethod
    def __rich__(self) -> RenderableType: ...

    @contextlib.contextmanager
    def __call__(self, *, transient: bool = True, force: bool = False) -> Generator[None]:
        if self.disabled and not force:
            yield
            return

        with disable_console_logging():
            if "pytest" in sys.modules and not force:
                yield
                return

            with Live(
                refresh_per_second=REFRESH_RATE.get(),
                auto_refresh=True,
                screen=transient,
                transient=transient,
                get_renderable=self.__rich__,
            ):
                yield
