from __future__ import annotations

import logging
import webbrowser
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)
_FILE_BROWSERS: tuple[str, ...]
_web_browsers = (
    "safari",
    "mozilla",
    "firefox",
    "edge",
    "chrome",
    "chromium",
    "opera",
    "epiphany",
    "www-browser",
    "links",
)


def browsers() -> tuple[str, ...]:
    global _FILE_BROWSERS  # noqa: PLW0603
    try:
        return _FILE_BROWSERS
    except NameError:
        _ = webbrowser.get()
        fbs: list[str] = []
        for name in webbrowser._tryorder:  # pyright: ignore[reportAttributeAccessIssue]
            if any(web in name for web in _web_browsers):
                continue
            fbs.append(name)

        _FILE_BROWSERS = tuple(fbs)  # pyright: ignore[reportConstantRedefinition]
        return _FILE_BROWSERS


def open(path: Path, new: Literal[0, 1, 2] = 0, *, autoraise: bool = True) -> bool:  # noqa: A001
    uri = str(path)
    input(tuple(browsers()))
    for name in browsers():
        browser = webbrowser.get(name)
        logger.debug("Trying to open '%s' with '%s'", browser.name, uri)
        if browser.open(uri, new, autoraise):
            return True

    logger.error("Unable to open '%s' with any file browser", uri)
    return False


def open_new(path: Path, *, autoraise: bool = True) -> bool:
    return open(path, new=1, autoraise=autoraise)
