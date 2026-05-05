from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import json
import shutil
import sys
import time
from contextvars import ContextVar
from typing import TYPE_CHECKING, Final

import rich
from rich.console import Group, RenderableType
from rich.layout import Layout

from cyberdrop_dl import env
from cyberdrop_dl.cli import UIOptions
from cyberdrop_dl.progress import LiveUI
from cyberdrop_dl.progress.scraping.downloads import DownloadsPanel
from cyberdrop_dl.progress.scraping.errors import DownloadErrorsPanel, ScrapeErrorsPanel
from cyberdrop_dl.progress.scraping.files import FileStatsPanel
from cyberdrop_dl.progress.scraping.panel import ScrapingPanel, StatusMessage

if TYPE_CHECKING:
    from collections.abc import Generator, Iterator

_PANEL_PADDING: Final = 5
_STATUS: ContextVar[StatusMessage] = ContextVar("_STATUS")
_WRITE_JSON: bool = True


@dataclasses.dataclass(slots=True, frozen=True)
class Screen:
    horizontal: Layout
    vertical: Layout

    def __iter__(self) -> Iterator[Layout]:
        return iter((self.horizontal, self.vertical))

    def __rich__(self) -> Layout:
        return self.vertical if terminal_is_in_portrait() else self.horizontal


@dataclasses.dataclass(slots=True)
class ScrapingUI(LiveUI):
    mode: UIOptions = UIOptions.FULLSCREEN
    files: FileStatsPanel = dataclasses.field(default_factory=FileStatsPanel)
    scrape_errors: ScrapeErrorsPanel = dataclasses.field(default_factory=ScrapeErrorsPanel)
    download_errors: DownloadErrorsPanel = dataclasses.field(default_factory=DownloadErrorsPanel)

    scrape: ScrapingPanel = dataclasses.field(default_factory=ScrapingPanel)
    downloads: DownloadsPanel = dataclasses.field(default_factory=DownloadsPanel)
    status: StatusMessage = dataclasses.field(default_factory=StatusMessage)
    _screen: Screen = dataclasses.field(init=False)
    _last_write: float | None = None

    def __post_init__(self) -> None:
        self._screen = self._create_screen()

    def __rich__(self) -> RenderableType:
        self._emit_jsonl()
        if self.mode is UIOptions.SIMPLE:
            renderable = Group(self.files.simple, self.status)
        elif self.mode is UIOptions.ACTIVITY:
            renderable = self.status

        else:
            renderable = self._screen

        return renderable

    def _emit_jsonl(self) -> None:
        now = time.monotonic()
        if self._last_write is None:
            self._last_write = now
        elif now - self._last_write < 5:
            return

        json.dump(self.__json__(), sys.stderr, ensure_ascii=False, separators=(",", ":"))
        sys.stderr.write("\n")
        sys.stderr.flush()
        self._last_write = now

    @contextlib.contextmanager
    def __call__(self, *, transient: bool = True, force: bool = False) -> Generator[None]:
        token = _STATUS.set(self.status)
        if self.mode is not UIOptions.FULLSCREEN:
            transient = False
        try:
            with super(ScrapingUI, self).__call__(transient=transient, force=force):
                yield
        finally:
            _STATUS.reset(token)

    def _create_screen(self) -> Screen:
        horizontal, vertical = Layout(), Layout()
        bottom = (
            Layout(self.scrape, name="scrape", size=self.scrape.max_rows + _PANEL_PADDING),
            Layout(self.downloads, name="downloads", minimum_size=10),
            Layout(self.status, name="status", size=2),
        )

        horizontal.split_column(Layout(name="top", size=self.scrape_errors.max_rows + _PANEL_PADDING), *bottom)
        horizontal["top"].split_row(
            Layout(self.files, name="files"),
            Layout(self.scrape_errors, name="scrape_errors"),
            Layout(self.download_errors, name="download_errors"),
        )

        vertical.split_column(
            Layout(self.files, name="files", size=9),
            Layout(self.scrape_errors, name="scrape_errors"),
            Layout(self.download_errors, name="download_errors"),
            *bottom,
        )

        return Screen(horizontal, vertical)

    def hide_scrape_panel(self) -> None:
        free_rows = self.scrape.max_rows + _PANEL_PADDING

        for layout in self._screen:
            layout["scrape"].visible = False
            layout["downloads"].minimum_size += free_rows

        self.downloads.max_rows += free_rows
        for _ in range(free_rows):
            try:
                self.downloads._push_one_invisible()
            except IndexError:
                break

    def __json__(self):
        return {
            "files": self.files.__json__(),
            "scrape_errors": self.scrape_errors.__json__(),
            "download_errors": self.download_errors.__json__(),
            "scraping": self.scrape.__json__(),
            "downloads": self.downloads.__json__(),
            "status": self.status.__json__(),
        }

    async def simulate(self) -> None:

        try:
            async with asyncio.timeout(30):
                async with asyncio.TaskGroup() as tg:
                    for panel in (
                        self.files,
                        self.scrape_errors,
                        self.download_errors,
                        self.downloads,
                        self.status,
                    ):
                        _ = tg.create_task(panel.simulate())

                    async def scrape() -> None:
                        await self.scrape.simulate()
                        self.hide_scrape_panel()

                    _ = tg.create_task(scrape())

        except TimeoutError:
            pass

        with show_msg("final msg"):
            await asyncio.sleep(3)


def terminal_is_in_portrait() -> bool:

    if env.PORTRAIT_MODE:
        return True

    terminal_size = shutil.get_terminal_size()
    width, height = terminal_size.columns, terminal_size.lines
    aspect_ratio = width / height

    # High aspect ratios are likely to be in landscape mode
    if aspect_ratio >= 3.2:
        return False

    # Check for mobile device in portrait mode
    if (aspect_ratio < 1.5 and height >= 40) or (aspect_ratio < 2.3 and width <= 85):
        return True

    # Assume landscape mode for other cases
    return False


@contextlib.contextmanager
def show_msg(msg: object) -> Generator[None]:
    with _STATUS.get()(msg):
        yield


if __name__ == "__main__":
    scrape_tui = ScrapingUI()
    rich.print(scrape_tui._screen.horizontal.tree)
    _ = input("press <ENTER> to continue")

    with scrape_tui(transient=False):
        asyncio.run(scrape_tui.simulate())
