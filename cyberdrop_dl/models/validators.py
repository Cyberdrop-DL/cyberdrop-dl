from __future__ import annotations

import re
from datetime import timedelta
from typing import TYPE_CHECKING, Literal, SupportsIndex, SupportsInt

from pydantic import ByteSize, TypeAdapter

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import yarl


_DATE_PATTERN_REGEX = r"(\d+)\s*(second|seconds|minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)"
_DATE_PATTERN = re.compile(_DATE_PATTERN_REGEX, re.IGNORECASE)
_BYTE_SIZE_ADAPTER = TypeAdapter(ByteSize)

type _ConvertibleToInt = str | SupportsInt | SupportsIndex


def bytesize_to_str(value: _ConvertibleToInt) -> str:
    return ByteSize(value).human_readable(decimal=True)


def to_yarl_url(value: object) -> yarl.URL:
    from cyberdrop_dl.utils import parse_url

    try:
        return parse_url(str(value))
    except Exception as e:
        raise ValueError(str(e)) from e


def to_bytesize(value: ByteSize | str | int) -> ByteSize:
    return _BYTE_SIZE_ADAPTER.validate_python(value)


def change_path_suffix(suffix: str) -> Callable[[Path], Path]:
    def with_suffix(value: Path) -> Path:
        return value.with_suffix(suffix)

    return with_suffix


def _str_to_timedelta(input_date: str) -> timedelta:
    time_str = input_date.casefold()
    matches: list[str] = re.findall(_DATE_PATTERN, time_str)
    seen_units: set[str] = set()
    time_dict: dict[str, int] = {"days": 0}

    for value, unit in matches:
        value = int(value)
        unit = unit.lower()
        normalized_unit = unit.rstrip("s")
        plural_unit = normalized_unit + "s"
        if normalized_unit in seen_units:
            msg = f"Duplicate time unit detected: '{unit}' conflicts with another entry"
            raise ValueError(msg)
        seen_units.add(normalized_unit)

        if "day" in unit:
            time_dict["days"] += value
        elif "month" in unit:
            time_dict["days"] += value * 30
        elif "year" in unit:
            time_dict["days"] += value * 365
        else:
            time_dict[plural_unit] = value

    if not matches:
        msg = f"Unable to convert '{input_date}' to timedelta object"
        raise ValueError(msg)
    return timedelta(**time_dict)


def to_timedelta(input_date: timedelta | str | int) -> timedelta | str:
    """Parses `datetime.timedelta`, `str` or `int` into a timedelta format.

    For `str`, the expected format is `<value> <unit>`, ex: `5 days`, `10 minutes`, `1 year`

    Valid units:
        `year(s)`, `week(s)`, `day(s)`, `hour(s)`, `minute(s)`, `second(s)`, `millisecond(s)`, `microsecond(s)`

    For `int`, `input_date` is assumed as `days`
    """
    input_date = falsy_as(input_date, timedelta(0))
    if isinstance(input_date, timedelta):
        return input_date
    if isinstance(input_date, int):
        return timedelta(days=input_date)
    try:
        return _str_to_timedelta(input_date)
    except Exception:  # noqa: BLE001
        return input_date  # Let pydantic try to validate this


def falsy_as[T, T2](value: T | Literal[""] | None, default: T2) -> T | T2:
    if isinstance(value, str) and value.casefold() in {"none", "null"}:
        return default

    return value or default


def falsy_as_list[T](value: list[T] | Literal[""] | None) -> list[T]:
    return falsy_as(value, [])


def falsy_as_none[T](value: T | Literal[""] | None) -> T | None:
    return falsy_as(value, None)
