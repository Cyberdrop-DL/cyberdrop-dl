from __future__ import annotations

import logging
import webbrowser
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal

from cyberdrop_dl import env

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

logger = logging.getLogger(__name__)
_FILE_BROWSERS: dict[str, webbrowser.BaseBrowser] = {}
_loaded: bool = False
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
    "w3m",
    "lynx",
    "elinks",
)


def browsers() -> Mapping[str, webbrowser.BaseBrowser]:
    if not _loaded:
        _register_file_browsers()
    return MappingProxyType(_FILE_BROWSERS)


def _register_file_browsers() -> None:
    global _loaded  # noqa: PLW0603
    try:
        _ = webbrowser.get()
    except webbrowser.Error:
        pass
    else:
        name: str
        for name in webbrowser._tryorder:  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
            if any(web in name for web in _web_browsers):
                continue
            _FILE_BROWSERS[name] = webbrowser.get(name)

    if env.RUNNING_IN_TERMUX:
        from cyberdrop_dl.utils.file_browser._termux import load_file_explorers

        _FILE_BROWSERS.update((fm.package_name, fm) for fm in load_file_explorers())

    _loaded = True


def open(path: Path, new: Literal[0, 1, 2] = 0, *, autoraise: bool = True) -> bool:  # noqa: A001
    uri = str(path)
    input(tuple(browsers().keys()))
    for name, browser in browsers().items():
        logger.debug("Trying to open '%s' with '%s'", uri, name)
        if browser.open(uri, new, autoraise):
            return True

    logger.error("Unable to open '%s' with any file browser", uri)
    return False


def open_new(path: Path, *, autoraise: bool = True) -> bool:
    return open(path, new=1, autoraise=autoraise)
