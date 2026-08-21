from __future__ import annotations

import logging
import webbrowser
from types import MappingProxyType
from typing import TYPE_CHECKING

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


logger.setLevel(logging.DEBUG if (env.DEBUG_MODE or env.RUNNING_IN_TERMUX) else logging.ERROR)


def get_file_browsers() -> Mapping[str, webbrowser.BaseBrowser]:
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
        from cyberdrop_dl.utils.file_browser._termux import ANDROID_FILE_MANAGERS, AndroidActivityManagerBrowser

        _FILE_BROWSERS.update(
            (fm.package_name, AndroidActivityManagerBrowser(fm.package_name, fm.activity))
            for fm in ANDROID_FILE_MANAGERS
            if not fm.skip
        )

    _loaded = True


def open_folder(path: Path) -> bool:
    assert path.is_dir()
    uri = str(path)
    file_browsers = get_file_browsers()
    if not file_browsers:
        logger.error("Unable to find any file browser on the system")
        return False

    logger.debug("File browsers to try (%s): \n- %s", len(file_browsers), "\n- ".join(file_browsers))

    logger.info("Opening '%s' with file explorer...", uri)
    for name, browser in list(file_browsers.items()):
        if browser.open(uri, new=1, autoraise=True):
            logger.info("Successfully opened '%s' with '%s'", uri, name)
            return True
        del _FILE_BROWSERS[name]

    logger.error("Unable to open '%s' with any file browser", uri)
    return False
