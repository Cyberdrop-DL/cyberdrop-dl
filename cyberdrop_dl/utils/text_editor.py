from __future__ import annotations

import functools
import logging
import os
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

type CMD = Sequence[str]

# Ordered by preference
_UNIX_TEXT_EDITORS: tuple[CMD, ...] = (
    ("micro", "-keymenu", "true"),
    ("nano",),
    ("vim",),
)


logger = logging.getLogger(__name__)


def open(file_path: Path) -> None:  # noqa: A001
    """Opens file in the OS's text editor."""
    cmd = *editor_cmd(), file_path
    logger.info(f"Opening '{file_path}' with '{cmd[0]}'...")
    _ = subprocess.call(cmd, stderr=subprocess.DEVNULL)


@functools.cache
def editor_cmd() -> CMD:
    cmd = _editor_cmd()
    if not cmd:
        msg = "No default text editor found"
        raise ValueError(msg)
    return cmd


def _editor_cmd() -> CMD | None:
    if editor := os.environ.get("EDITOR"):
        if shutil.which(editor):
            return (editor,)

        import shlex

        cmd = shlex.split(editor)
        if cmd and shutil.which(cmd[0]):
            return cmd

        msg = f"Editor '{editor}' from env var $EDITOR is not available. Ignoring"
        logger.warning(msg)

    if sys.platform == "darwin":
        return "open", "-t", "-n", "-W"

    if sys.platform == "win32":
        return _find_win_editor()

    return _find_unix_editor()


def _find_win_editor() -> CMD | None:
    for notepad_pp in map(
        os.path.expandvars,
        [
            "%PROGRAMFILES%/Notepad++/notepad++.exe",
            "%PROGRAMFILES(X86)%/Notepad++/notepad++.exe",
        ],
    ):
        if shutil.which(notepad_pp):
            return notepad_pp, "-multiInst", "-noPlugin", "-notabbar", "-nosession"

    if shutil.which(notepad := "notepad.exe"):
        return (notepad,)


def _find_unix_editor() -> CMD | None:
    has_desktop_enviroment = any(var in os.environ for var in ("DISPLAY", "WAYLAND_DISPLAY"))
    if has_desktop_enviroment and "SSH_CONNECTION" not in os.environ and _set_xdg_yaml_default_if_none():
        return ("xdg-open",)

    for cmd in _UNIX_TEXT_EDITORS:
        if shutil.which(cmd[0]):
            return cmd


def _set_xdg_yaml_default_if_none() -> bool:
    """
    Ensures YAML's MIME type has a default XDG app, falling back to whatever app is currently set for 'text/plain'

    Returns `True` if a default app is now associated, `False` if setting the default failed
    """
    yaml_mime = "application/yaml"
    text_mime = "text/plain"

    def xdg_query_default(mimetype: str) -> str:
        cmd = "xdg-mime", "query", "default", mimetype
        process = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return process.stdout.strip()

    if xdg_query_default(yaml_mime):
        return True

    default_text_app = xdg_query_default(text_mime)
    if not default_text_app:
        return False

    return subprocess.call(["xdg-mime", "default", default_text_app, yaml_mime]) == 0
