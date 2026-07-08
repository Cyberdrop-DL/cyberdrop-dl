from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import inquirer
import inquirer.questions
from inquirer.themes import BlueComposure
from rich.console import Console
from rich.text import Text

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


_ERROR = Text("ERROR:  ", style="bold red")
_WARNING = Text("WARNING:", style="bold yellow")


class _ConsoleWrapper:
    def __init__(self, console: Console | None = None) -> None:
        self.console: Console = console or Console()

    def info(self, *objects: object) -> None:
        self.console.print(*objects)

    def warning(self, *objects: object) -> None:
        self.console.print(_WARNING, *objects)

    def error(self, *objects: object) -> None:
        self.console.print(_ERROR, *objects)

    def rule(self, color: str = "blue") -> None:
        self.console.rule(style=color)

    def line(self, count: int = 1) -> None:
        self.console.line(count)

    def input(self, msg: str = "") -> None:
        self.console.input(msg)

    def clear(self) -> None:
        _ = os.system("cls" if os.name == "nt" else "clear")  # noqa: S605


console = _ConsoleWrapper()


def enter_to_continue() -> None:
    if "pytest" in sys.modules:
        return
    console.rule()
    console.input("Press <ENTER> to continue")


def ask(question: inquirer.questions.Question) -> Any:
    answers = inquirer.prompt([question], raise_keyboard_interrupt=True, theme=BlueComposure())
    assert answers
    return next(iter(answers.values()))


def ask_choices[T](choices: Iterable[T]) -> T:
    return ask(inquirer.List("main", message="What would you like to do", choices=list(choices)))


def ask_text(text: str, default: object | None = None) -> str:
    return ask(inquirer.Text("text", message=text, default=default))


def ask_confirmation(text: str = "", *, explicit: bool = False) -> bool:
    if explicit:
        msg = "Type 'YES' to proceed"
        answer = ask_text(f"{text}. {msg}" if text else msg)
        return answer.strip().casefold() == "yes"
    return ask(inquirer.Confirm("text", message=text))


def ask_dir(message: str = "Select dir path", default: Path | None = None) -> Path:

    def is_dir(path: Path) -> None:
        if not path.is_dir():
            raise NotADirectoryError(str(path))

    return ask_path(message, default, validate=is_dir)


def ask_path(
    message: str = "Select path",
    default: Path | None = None,
    *,
    validate: Callable[[Path], None] | None = None,
    must_exists: bool = True,
) -> Path:
    while True:
        try:
            answer = ask_text(message, default=default or Path.home())
            path = Path(answer).expanduser()
            if must_exists and not path.exists():
                raise FileNotFoundError(answer)
            if validate:
                validate(path)

        except OSError as e:
            console.error(repr(e))
        else:
            return path.resolve()


def ask_should_create_config(file: Path) -> bool:
    console.warning("A default config file does not exists")
    return ask_confirmation(f"Do you want to create it at '{file}'?")
