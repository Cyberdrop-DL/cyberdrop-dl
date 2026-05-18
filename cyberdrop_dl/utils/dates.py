from __future__ import annotations

import asyncio
import datetime
import email.utils
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING, NewType

if TYPE_CHECKING:
    from pathlib import Path


if sys.platform == "win32":
    # Try to import win32con for Windows constants, fallback to hardcoded values if unavailable
    try:
        import win32con  # type: ignore[reportMissingModuleSource]  # pyright: ignore[reportMissingModuleSource]

    except ImportError:
        win32con = None

    FILE_WRITE_ATTRIBUTES = 256
    OPEN_EXISTING = win32con.OPEN_EXISTING if win32con else 3
    FILE_ATTRIBUTE_NORMAL = win32con.FILE_ATTRIBUTE_NORMAL if win32con else 128
    FILE_FLAG_BACKUP_SEMANTICS = win32con.FILE_FLAG_BACKUP_SEMANTICS if win32con else 33554432

    # Windows epoch is January 1, 1601. Unix epoch is January 1, 1970
    WIN_EPOCH_OFFSET = 116444736e9

    from ctypes import byref, windll, wintypes

    def _set_win_time(file: Path, datetime: float) -> None:
        nano_ts: float = datetime * 1e7  # Windows uses nano seconds for dates
        timestamp = int(nano_ts + WIN_EPOCH_OFFSET)

        # Windows dates are 64bits, split into 2 32bits unsigned ints (dwHighDateTime , dwLowDateTime)
        # XOR to get the date as bytes, then shift to get the first 32 bits (dwHighDateTime)
        ctime = wintypes.FILETIME(timestamp & 0xFFFFFFFF, timestamp >> 32)
        access_mode = FILE_WRITE_ATTRIBUTES
        sharing_mode = 0  # Exclusive access
        security_mode = None  # Use default security attributes
        creation_disposition = OPEN_EXISTING

        # FILE_FLAG_BACKUP_SEMANTICS allows access to directories
        flags = FILE_ATTRIBUTE_NORMAL | FILE_FLAG_BACKUP_SEMANTICS
        template_file = None

        params = (
            access_mode,
            sharing_mode,
            security_mode,
            creation_disposition,
            flags,
            template_file,
        )

        handle = windll.kernel32.CreateFileW(str(file), *params)
        windll.kernel32.SetFileTime(
            handle,
            byref(ctime),  # Creation time
            None,  # Access time
            None,  # Modification time
        )
        windll.kernel32.CloseHandle(handle)

    async def set_creation_time(file: Path, timestamp: float) -> None:
        return await asyncio.to_thread(_set_win_time, file, timestamp)


elif sys.platform == "darwin" and (MAC_OS_SET_FILE := shutil.which("SetFile") or ""):
    # SetFile is non standard in macOS. Only users that have xcode installed will have SetFile

    async def set_creation_time(file: Path, timestamp: float) -> None:
        time_string = from_timestamp(timestamp).strftime("%m/%d/%Y %H:%M:%S")
        process = await asyncio.subprocess.create_subprocess_exec(
            MAC_OS_SET_FILE,
            "-d",
            time_string,
            file,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _ = await process.wait()

else:

    async def set_creation_time(file: Path, timestamp: float) -> None: ...


TimeStamp = NewType("TimeStamp", int)
UTCAwareDatetime = NewType("UTCAwareDatetime", datetime.datetime)


def _normalize(date_time: datetime.datetime) -> UTCAwareDatetime:
    date_time = date_time.astimezone(datetime.UTC)
    if date_time.microsecond:
        date_time = date_time.replace(microsecond=0)
    return UTCAwareDatetime(date_time)


def parse_iso(date_or_datetime: str, /) -> UTCAwareDatetime:
    return _normalize(datetime.datetime.fromisoformat(date_or_datetime))


def parse_format(date_or_datetime: str, /, format: str) -> UTCAwareDatetime:  # noqa: A002
    return _normalize(datetime.datetime.strptime(date_or_datetime, format))  # noqa: DTZ007


def parse_http(date: str, /) -> TimeStamp:
    """parse rfc 2822 or an "HTTP-date" format as defined by RFC 9110"""
    return to_timestamp(_normalize(email.utils.parsedate_to_datetime(date)))


def parse_timestamp_from_iso(date_or_datetime: str, /) -> TimeStamp:
    return to_timestamp(parse_iso(date_or_datetime))


def to_timestamp(date: datetime.datetime) -> TimeStamp:
    return TimeStamp(int(date.timestamp()))


def from_timestamp(timestamp: float) -> UTCAwareDatetime:
    return _normalize(datetime.datetime.fromtimestamp(timestamp, tz=datetime.UTC))


def now() -> datetime.datetime:
    return datetime.datetime.now()  # noqa: DTZ005


def now_utc() -> UTCAwareDatetime:
    return _normalize(now())


MIN = _normalize(datetime.datetime.min.replace(tzinfo=datetime.UTC))
MAX = _normalize(datetime.datetime.max.replace(tzinfo=datetime.UTC))
