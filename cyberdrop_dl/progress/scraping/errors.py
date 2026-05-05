from __future__ import annotations

import asyncio
import dataclasses
import functools
import random
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, Final, Self

import rich
from rich.console import Group
from rich.panel import Panel
from rich.progress import BarColumn, TaskID, TextColumn

from cyberdrop_dl.progress import DictProgress, create_test_live
from cyberdrop_dl.progress.overflow import OverFlow

if TYPE_CHECKING:
    from collections.abc import Iterator

_ACRONYMS = frozenset(("HTTP", "URL", "DNS"))


@functools.cache
def _pretty_format(error: str) -> str:
    return _ERROR_OVERRIDES.get(error) or _capitalize_words(error)


def _capitalize_words(text: str) -> str:
    """Capitalize first letter of each word

    Unlike `str.title()`, this caps the first letter of each word without modifying the rest of the word"""

    def cap(word: str) -> str:
        if word in _ACRONYMS:
            return word
        return word[0].upper() + word[1:]

    return " ".join([cap(word) for word in text.split()])


@dataclasses.dataclass(slots=True, order=True)
class UIError:
    msg: str
    count: int
    code: int | None = None

    @classmethod
    def parse(cls, msg: str, count: int) -> Self:
        if len(parts := msg.split(" ", 1)) == 2:
            error_code, real_msg = parts
            try:
                return cls(real_msg, count, int(error_code))
            except ValueError:
                pass

        return cls(msg, count)

    def format(self, padding: int = 0) -> str:
        error_code = self.code if self.code is not None else ""
        return f"{error_code:>{padding}}{' ' if padding or error_code else ''}{self.msg}: {self.count:,}"


class _ErrorsPanel:
    """Base class that keeps track of errors and reasons."""

    title: ClassVar[str]
    max_rows: Final[int] = 7

    def __repr__(self) -> str:
        return f"{type(self).__name__}(error_count={self._total!r}, errors={tuple(self._errors_map)!r})"

    def __init__(self) -> None:
        self._progress: DictProgress = DictProgress(
            "[progress.description]{task.description}",
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>6.2f}%",
            "•",
            TextColumn("{task.completed:,}", justify="right"),
        )
        self._overflow: OverFlow = OverFlow("kind of error")
        self._errors_map: dict[str, TaskID] = {}
        self._total: int = 0
        self._changed: bool = False
        self._panel: Panel = Panel(
            Group(self._progress, self._overflow),
            title=f"{self.title} Errors",
            border_style="green",
            padding=(1, 1),
        )

    def __rich__(self) -> Panel:
        if self._changed:
            self._sort_tasks()
            self._changed = False

        self._panel.subtitle = f"Total: [white]{self._total:,}"
        return self._panel

    def add(self, error: str) -> None:
        self._total += 1
        name = _pretty_format(error)
        if (task_id := self._errors_map.get(name)) is not None:
            self._progress.advance(task_id)
        else:
            self._overflow.count = len(self._errors_map) + 1 - self.max_rows
            self._errors_map[name] = self._progress.add_task(
                name,
                total=self._total,
                completed=1,
                visible=not self._overflow,
            )

        self._changed = True

    def _sort_tasks(self) -> None:
        for task_id in self._errors_map.values():
            self._progress.update(task_id, total=self._total)

        self._progress.sort_tasks(
            lambda tasks: sorted(tasks, key=lambda x: x.completed, reverse=True),
        )

    def __iter__(self) -> Iterator[UIError]:
        tasks = {task.id: task for task in self._progress.tasks}
        return iter((UIError.parse(msg, int(tasks[task_id].completed)) for msg, task_id in self._errors_map.items()))

    async def simulate(self) -> None:
        self.add("404 not found")
        for error in random.choices(tuple(_ERROR_OVERRIDES), k=40):
            self.add(error)
            await asyncio.sleep(random.random())

    def __json__(self) -> dict[str, Any]:
        return {"errors": tuple(dataclasses.asdict(error) for error in self)}


class DownloadErrorsPanel(_ErrorsPanel):
    title: ClassVar[str] = "Download"


class ScrapeErrorsPanel(_ErrorsPanel):
    title: ClassVar[str] = "Scrape"

    def __init__(self) -> None:
        super().__init__()
        self._unsupported: int = 0
        self.sent_to_jdownloader: int = 0
        self.skipped: int = 0

    def add_unsupported(self, *, sent_to_jdownloader: bool = False) -> None:
        self._unsupported += 1
        if sent_to_jdownloader:
            self.sent_to_jdownloader += 1
        else:
            self.skipped += 1

    def __json__(self) -> dict[str, Any]:
        me = super().__json__()
        me.update(sent_to_jdownloader=self.sent_to_jdownloader, skipped=self.skipped)
        return me


_ERROR_OVERRIDES = MappingProxyType(
    {
        "ClientConnectorCertificateError": "Client Connector Certificate Error",
        "ClientConnectorDNSError": "Client Connector DNS Error",
        "ClientConnectorError": "Client Connector Error",
        "ClientConnectorSSLError": "Client Connector SSL Error",
        "ClientHttpProxyError": "Client HTTP Proxy Error",
        "ClientPayloadError": "Client Payload Error",
        "ClientProxyConnectionError": "Client Proxy Connection Error",
        "ConnectionTimeoutError": "Connection Timeout",
        "ContentTypeError": "Content Type Error",
        "InvalidURL": "Invalid URL",
        "InvalidUrlClientError": "Invalid URL Client Error",
        "InvalidUrlRedirectClientError": "Invalid URL Redirect",
        "NonHttpUrlRedirectClientError": "Non HTTP URL Redirect",
        "RedirectClientError": "Redirect Error",
        "ServerConnectionError": "Server Connection Error",
        "ServerDisconnectedError": "Server Disconnected",
        "ServerFingerprintMismatch": "Server Fingerprint Mismatch",
        "ServerTimeoutError": "Server Timeout Error",
        "SocketTimeoutError": "Socket Timeout Error",
    }
)


if __name__ == "__main__":
    panel = DownloadErrorsPanel()
    with create_test_live(panel, transient=True):
        asyncio.run(panel.simulate())
        rich.print(sorted(panel))

    rich.print(panel.__json__())
