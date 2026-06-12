from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from cyberdrop_dl import tracebacks
from cyberdrop_dl.cli import app
from cyberdrop_dl.exceptions import CDLConfigRuntimeErrorsGroup, DatabaseError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from rich.console import RenderableType
    from rich.panel import Panel

tracebacks.install_exception_hook()


def _error_panel(message: RenderableType, title: str = "Error") -> Panel:
    # Based on the default cyclopts panel
    from rich import box
    from rich.panel import Panel

    return Panel(
        message,
        title=title,
        box=box.ROUNDED,
        border_style="red",
        expand=True,
        title_align="left",
    )


def run_cdl(args: Sequence[str] | None = None) -> int:
    from pydantic import ValidationError

    from cyberdrop_dl.logs import setup_console_logging

    with setup_console_logging():
        try:
            app(args)
        except (ValidationError, DatabaseError) as exc:
            tb = tracebacks.from_exception(exc.with_traceback(None), chain_traceback=False)
            app.console.print(_error_panel(tb))
        except CDLConfigRuntimeErrorsGroup as exc_group:
            tb = tracebacks.from_exception(exc_group, chain_traceback=False)
            app.console.print(_error_panel(tb, title="Invalid Config"))
        else:
            return 0

        return 1


def main(args: Sequence[str] | None = None) -> None:
    sys.exit(run_cdl(args))


if __name__ == "__main__":
    main()
