"""async aware and thread safe global state

Only define contextvars here if the module that uses them is different from the module that sets them

- They MUST be used across multiple modules
- Their inner type SHOULD NOT be a custom CDL type (except objects in url_objects)
- This module MUST NOT import any other CDL module
"""

from __future__ import annotations

import contextlib
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from cyberdrop_dl.url_objects import AbsoluteHttpURL

ALLOW_NO_EXT: ContextVar[bool] = ContextVar("ALLOW_NO_EXT", default=False)
CHECK_DL_CAPACITY: ContextVar[bool] = ContextVar("CHECK_DL_CAPACITY")
CONCURRENT_SEGMENTS: ContextVar[int] = ContextVar("CONCURRENT_SEGMENTS")
IGNORE_CONTENT_TYPE: ContextVar[bool] = ContextVar("IGNORE_CONTENT_TYPE", default=False)
MAIN_LOG_FILE: ContextVar[Path] = ContextVar("MAIN_LOG_FILE")
ORIGIN: ContextVar[AbsoluteHttpURL] = ContextVar("ORIGIN")
REFRESH_RATE: ContextVar[float] = ContextVar("REFRESH_RATE", default=10.0)
SKIP_DOWNLOAD: ContextVar[bool] = ContextVar("SKIP_DOWNLOAD", default=False)
TUI_DISABLED: ContextVar[bool] = ContextVar("TUI_DISABLED", default=False)
USE_RETRY_PATH: ContextVar[bool] = ContextVar("USE_RETRY_PATH", default=False)


@contextlib.contextmanager
def enter[T](context_var: ContextVar[T], value: T, /) -> Generator[None]:
    token = context_var.set(value)
    try:
        yield
    finally:
        context_var.reset(token)


def setdefault[T](context_var: ContextVar[T], value: T, /) -> contextlib.AbstractContextManager[None]:
    current = context_var.get(None)
    if current is None:
        return enter(context_var, value)
    return contextlib.nullcontext()
