# ruff: noqa: E402
import logging
import sys
from collections.abc import Sequence

from cyclopts import CycloptsPanel

from cyberdrop_dl import tracebacks

tracebacks.install_exception_hook()

from cyberdrop_dl.cli import app
from cyberdrop_dl.logs import setup_console_logging

logger = logging.getLogger("cyberdrop_dl")


def main(args: Sequence[str] | None = None) -> int | None:
    with setup_console_logging():
        try:
            app(args)
            return 0
        except* ValueError as exc_group:
            msg = "\n" + "\n".join(map(str, exc_group.exceptions))
            app.console.print(CycloptsPanel(msg, title=exc_group.message))


if __name__ == "__main__":
    sys.exit(bool(main()))
