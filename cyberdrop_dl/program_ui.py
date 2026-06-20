from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiohttp
import inquirer
import inquirer.questions
from inquirer.themes import BlueComposure
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

from cyberdrop_dl import __version__, stats
from cyberdrop_dl.hasher import Hasher, hash_directory
from cyberdrop_dl.progress import hyperlink
from cyberdrop_dl.sorter import Sorter
from cyberdrop_dl.utils import text_editor

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from cyberdrop_dl.manager import Manager


_CONSOLE = Console()
_ERROR = Text("ERROR: ", style="bold red")
_WARNING = Text("WARNING: ", style="bold yellow")
_CHANGELOG_URL = "https://raw.githubusercontent.com/Cyberdrop-DL/cyberdrop-dl/refs/heads/main/CHANGELOG.md"
_changelog: str = ""


def changelog() -> str:
    global _changelog  # noqa: PLW0603
    if not _changelog:
        _changelog = asyncio.run(_fetch_changelog())

    return _changelog


def run(manager: Manager) -> None:
    choices: dict[str, Callable[[Manager], bool | None]] = {
        "Download": lambda _: True,
        "Create file hashes": _scan_and_create_hashes,
        "Sort files in download folder": _sort_files,
        "Edit URLs.txt": _edit_urls,
        "Edit config": _edit_config,
        "View changelog": lambda _: _view_changelog(),
        "Exit": lambda _: sys.exit(0),
    }

    while True:
        _app_header(manager)
        answer = _ask_choices(choices)
        done = choices[answer](manager)
        if done:
            break


def _scan_and_create_hashes(manager: Manager) -> None:
    path = _ask_dir(
        "Select the directory to scan",
        default=manager.config.download_folder,
    )
    hasher = Hasher.create(manager.config, manager.database, path)
    hash_stats = asyncio.run(hash_directory(hasher))
    stats.print(hash_stats)
    _enter_to_continue()


def _sort_files(manager: Manager) -> None:
    sorter = Sorter.from_manager(manager)
    _CONSOLE.print(
        _WARNING,
        f"You are about to sort files from '{sorter.input_dir}' to '{sorter.output_dir}'",
    )
    if _ask_confirmation(explicit=True):
        asyncio.run(sorter.run())
        _enter_to_continue()


def _should_create_config(file: Path) -> bool:
    _CONSOLE.print(_WARNING, "A default config file does not exists")
    return _ask_confirmation(f"Do you want to create it at '{file}'?")


def _edit_config(manager: Manager) -> None:
    file = manager.config.source
    if file is None:
        file = manager.appdata.config_file
        if not _should_create_config(file):
            return
        type(manager.config)().save_to(file)

    try:
        text_editor.open(file)
    except ValueError as e:
        _CONSOLE.print(_ERROR, str(e))
    else:
        _CONSOLE.print(_WARNING, "You must restart cyberdrop-dl for changes to the config to take effect")
    finally:
        _enter_to_continue()


def _edit_urls(manager: Manager) -> None:
    try:
        text_editor.open(manager.input_file)
    except ValueError as e:
        _CONSOLE.print(_ERROR, str(e))
        _enter_to_continue()


async def _fetch_changelog() -> str:
    async with aiohttp.request(
        "GET",
        _CHANGELOG_URL,
        raise_for_status=True,
    ) as response:
        return await response.text()


def _view_changelog() -> None:
    _clear_term()
    try:
        content = changelog()
    except Exception as e:  # noqa: BLE001
        _CONSOLE.print(_ERROR, "UNABLE TO GET CHANGELOG INFORMATION", repr(e))
        _enter_to_continue()
        return

    with _CONSOLE.pager(links=True):
        _CONSOLE.print(Markdown(content, justify="left"))


def _app_header(manager: Manager) -> None:
    _clear_term()
    _CONSOLE.print(f"[bold]cyberdrop-dl ([blue]v{__version__!s}[/blue])[/bold]")
    _CONSOLE.rule(style="blue")
    paths = {
        "Config file": manager.config.source,
        "Database file": manager.appdata.db_file,
        "URLs file": manager.input_file,
        "Cache file": manager.appdata.cache_file,
        "Logs": manager.config.logs.effective_log_folder,
        "Main log file": manager.config.logs.files.main,
    }
    padding = max(map(len, paths))
    for name, file in paths.items():
        _CONSOLE.print(f"{name:<{padding}} :", hyperlink(file) if file else None)

    _CONSOLE.line()


def _ask_choices[T](choices: Iterable[T]) -> T:
    return _ask(  # pyright: ignore[reportAny]
        inquirer.List(
            "main",
            message="What would you like to do",
            choices=list(choices),
        )
    )


def _ask(question: inquirer.questions.Question) -> Any:
    answers = inquirer.prompt(
        [question],
        raise_keyboard_interrupt=True,
        theme=BlueComposure(),
    )
    assert answers
    return next(iter(answers.values()))


def _ask_text(text: str) -> str:
    return _ask(inquirer.Text("text", message=text))


def _ask_confirmation(text: str = "", *, explicit: bool = False) -> bool:
    if explicit:
        msg = "Type 'YES' to proceed"
        answer = _ask_text(f"{text}. {msg}" if text else msg)
        return answer.strip().casefold() == "yes"
    return _ask(inquirer.Confirm("text", message=text))


def _ask_dir(message: str = "Select dir path", default: Path | None = None) -> Path:

    def is_dir(path: Path) -> None:
        if not path.is_dir():
            raise NotADirectoryError(str(path))

    return _ask_path(message, default, validate=is_dir)


def _ask_file(message: str = "Select file", default: Path | None = None) -> Path:

    def is_file(path: Path) -> None:
        if not path.is_file():
            raise IsADirectoryError(str(path))

    return _ask_path(message, default, validate=is_file)


def _ask_path(
    message: str = "Select path",
    default: Path | None = None,
    *,
    validate: Callable[[Path], None] | None = None,
    must_exists: bool = True,
) -> Path:
    while True:
        try:
            answer = _ask(
                inquirer.Text(
                    "path",
                    message=message,
                    default=default or Path.home(),
                )
            )

            path = Path(answer).expanduser()
            if must_exists and not path.exists():
                raise FileNotFoundError(answer)
            if validate:
                validate(path)

        except OSError as e:
            _CONSOLE.print(_ERROR, repr(e))
        else:
            return path.resolve()


def _enter_to_continue() -> None:
    if "pytest" in sys.modules:
        return
    _ = input("Press <ENTER> to continue")


def _clear_term() -> None:
    _ = os.system("cls" if os.name == "nt" else "clear")  # noqa: S605
