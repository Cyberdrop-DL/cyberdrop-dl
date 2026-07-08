from __future__ import annotations

import contextlib
import dataclasses
import shutil
import sys
from abc import ABC, abstractmethod
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Protocol, Self

from rich.progress import Progress, Task, TaskID
from rich.text import Text

from cyberdrop_dl import env
from cyberdrop_dl.logs import disable_console_logging

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable
    from pathlib import Path

    from rich.console import RenderableType
    from rich.live import Live

REFRESH_RATE: ContextVar[float] = ContextVar("REFRESH_RATE", default=10.0)
TUI_DISABLED: ContextVar[bool] = ContextVar("TUI_DISABLED", default=False)
_in_portrait: bool = False


class Color:
    PLUM: str = "plum3"
    YELLOW: str = "yellow"


class JsonableRenderableType(Protocol):
    def __rich__(self) -> RenderableType: ...

    def __json__(self) -> Any: ...


class DisabledInPortraitMixin:
    def render(self, task: Task) -> Text:
        if _in_portrait:
            return Text("")
        return super().render(task)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportAttributeAccessIssue]


def _is_terminal_in_portrait() -> bool:

    if env.FORCE_PORTRAIT_MODE:
        return True

    terminal_size = shutil.get_terminal_size()
    width, height = terminal_size.columns, terminal_size.lines
    aspect_ratio = width / height

    # High aspect ratios are likely to be in landscape mode
    if aspect_ratio >= 3.2:
        return False

    # Check for mobile device in portrait mode, Assume landscape mode for other cases
    return (aspect_ratio < 1.5 and height >= 40) or (aspect_ratio < 2.3 and width <= 85)


def is_terminal_in_portrait() -> bool:
    global _in_portrait  # noqa: PLW0603
    _in_portrait = _is_terminal_in_portrait()
    return _in_portrait


def create_test_live(renderable: JsonableRenderableType, *, transient: bool = False, json: bool = True) -> Live:
    from rich.json import JSON
    from rich.live import Live

    if json:

        def get_renderable() -> RenderableType:
            return JSON.from_data(renderable.__json__())

    else:
        get_renderable = renderable.__rich__

    return Live(
        auto_refresh=True,
        refresh_per_second=20,
        transient=transient,
        get_renderable=get_renderable,
    )


def hyperlink(file_path: Path | str, text: str | None = None) -> Text:
    from rich.markup import escape
    from rich.text import Text

    text = escape(text or str(file_path))
    link = file_path if isinstance(file_path, str) else file_path.as_uri()
    return Text.from_markup(f"[link={link}]{text}[/link]", style="blue")


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

    def __enter__(self) -> Self:
        if self._done:
            raise RuntimeError
        return self

    def __exit__(self, *_: object) -> None:
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
        from rich.live import Live

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
                redirect_stderr=False,
            ):
                yield


def strip_markup(text: str) -> str:
    from rich.markup import _parse

    def parse() -> Generator[str]:
        for _position, plain_text, _tag in _parse(text):
            if plain_text is not None:
                yield plain_text.replace("\\[", "[")

    return "".join(parse())


def truncate_float(value: float | None, precision: int = 3) -> float | None:
    if value is None:
        return None
    return round(value, precision)
