from __future__ import annotations

import functools
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

_TEXT_EDITORS = "micro", "nano", "vim"  # Ordered by preference
_SSH = "SSH_CONNECTION" in os.environ
_HAS_DESKTOP_ENVIROMENT = any(var in os.environ for var in ("DISPLAY", "WAYLAND_DISPLAY"))
_CUSTOM_EDITOR = os.environ.get("EDITOR")
_YAML_MIMETYPE = "application/yaml"
_TEXT_MIMETYPE = "text/plain"

logger = logging.getLogger(__name__)


def open(file_path: Path) -> None:  # noqa: A001
    """Opens file in the OS's text editor."""

    cmd = _editor_cmd()
    if not cmd:
        msg = "No default text editor found"
        raise ValueError(msg)

    cmd = *cmd, file_path
    bin_path, *rest = cmd
    if Path(bin_path).stem == "micro":
        cmd = bin_path, "-keymenu", "true", *rest

    logger.info(f"Opening '{file_path}' with '{bin_path}'...")
    _ = subprocess.call(cmd, stderr=subprocess.DEVNULL)


@functools.cache
def _editor_cmd() -> tuple[str, ...] | None:
    if _CUSTOM_EDITOR:
        path = shutil.which(_CUSTOM_EDITOR)
        if path:
            return (path,)
        msg = f"Editor '{_CUSTOM_EDITOR}' from env bar $EDITOR is not available. Ignoring"
        logger.warning(msg)

    if sys.platform == "darwin":
        return "open", "-a", "TextEdit"

    if sys.platform == "win32":
        return ("notepad.exe",)

    if _HAS_DESKTOP_ENVIROMENT and not _SSH and _set_xdg_yaml_default_if_none():
        return ("xdg-open",)

    if fallback_editor := _find_text_editor():
        return (fallback_editor,)


def _find_text_editor() -> str | None:
    for editor in _TEXT_EDITORS:
        if bin_path := shutil.which(editor):
            return bin_path


def _set_xdg_yaml_default_if_none() -> bool:
    """
    Ensures YAML's MIME type has a default XDG app, falling back to whatever app is currently set for 'text/plain'

    Returns `True` if a default app is now associated, `False` if setting the default failed
    """

    def xdg_query_default(mimetype: str) -> str:
        cmd = "xdg-mime", "query", "default", mimetype
        process = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return process.stdout.strip()

    if xdg_query_default(_YAML_MIMETYPE):
        return True

    default_text_app = xdg_query_default(_TEXT_MIMETYPE)
    if not default_text_app:
        return False

    return subprocess.call(["xdg-mime", "default", default_text_app, _YAML_MIMETYPE]) == 0
