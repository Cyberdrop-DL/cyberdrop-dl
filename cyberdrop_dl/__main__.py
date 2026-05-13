import sys
from collections.abc import Sequence

from cyclopts import CycloptsPanel

from cyberdrop_dl import tracebacks
from cyberdrop_dl.cli import app

tracebacks.install_exception_hook()


def run_cdl(args: Sequence[str] | None = None) -> int | None:
    from cyberdrop_dl.logs import setup_console_logging

    with setup_console_logging():
        try:
            app(args)
            return 0
        except* ValueError as exc_group:
            msg = "\n" + "\n".join(map(str, exc_group.exceptions))
            app.console.print(CycloptsPanel(msg, title=exc_group.message))


def main(args: Sequence[str] | None = None):
    sys.exit(bool(run_cdl(args)))


if __name__ == "__main__":
    main()
