from __future__ import annotations

import datetime
import email.utils
import warnings
from functools import lru_cache
from typing import TYPE_CHECKING, Literal, NewType, ParamSpec, TypeAlias, TypeVar

import dateparser.date

if TYPE_CHECKING:
    from collections.abc import Callable

TimeStamp = NewType("TimeStamp", int)
DateOrder: TypeAlias = Literal["DMY", "DYM", "MDY", "MYD", "YDM", "YMD"]
ParserKind: TypeAlias = Literal["timestamp", "relative-time", "custom-formats", "absolute-time", "no-spaces-time"]

_S = TypeVar("_S", bound=str)
_P = ParamSpec("_P")
_R = TypeVar("_R", bound=datetime.datetime | None)

_DEFAULT_PARSERS: list[ParserKind] = ["relative-time", "custom-formats", "absolute-time", "no-spaces-time"]
_DEFAULT_DATE_ORDER = "MDY"


def _coerce_to_list(value: _S | set[_S] | list[_S] | tuple[_S, ...] | None) -> list[_S]:
    if value is None:
        return []
    if isinstance(value, tuple | set):
        return list(value)
    if isinstance(value, list):
        return value
    return [value]


class DateParser(dateparser.date.DateDataParser):
    """Parses incomplete dates, but they must have at least a known year and month

    Parsed dates are guaranteed to be in the past with time at midnight (if unknown)

    It can parse date strings like:

    `relative-time`:
    >>> "Today"
    >>> "Yesterday"
    >>> "1 hour ago"
    >>> "1 year, 2 months ago"
    >>> "3 hours, 50 minutes ago

    `absolute-time`:
    >>> "Fri, 12 Dec 2014 10:55:50"

    `no-spaces-time`:
    >>> "10032022"

    `timestamp`:
    >>> "1747880678"

    `custom-formats`
    """

    def __init__(
        self, parsers: list[ParserKind] | ParserKind | None = None, date_order: DateOrder | None = None
    ) -> None:
        date_order = date_order or _DEFAULT_DATE_ORDER
        parsers = _coerce_to_list(parsers) or _DEFAULT_PARSERS
        super().__init__(
            languages=["en"],
            try_previous_locales=True,
            settings={
                "DATE_ORDER": date_order,
                "PREFER_DAY_OF_MONTH": "first",
                "PREFER_DATES_FROM": "past",
                "REQUIRE_PARTS": ["month"],
                "RETURN_TIME_AS_PERIOD": True,
                "PARSERS": parsers,
            },
        )

    def parse_with_locales(
        self, date_string: str, date_formats: list[str] | str | None = None
    ) -> tuple[datetime.datetime, str] | tuple[None, None]:
        date_string = dateparser.date.sanitize_date(date_string)
        date_formats = _coerce_to_list(date_formats)
        parse = dateparser.date._DateLocaleParser.parse
        for locale in self._get_applicable_locales(date_string):
            date_data = parse(locale, date_string, date_formats, settings=self._settings)
            if not date_data or not date_data.date_obj:
                continue

            return date_data.date_obj, date_data.period or ""
        return None, None

    def parse_possible_incomplete_date(
        self, date_string: str, date_formats: list[str] | str | None = None
    ) -> datetime.datetime | None:
        """Adds current year to the date if it is missing from it"""
        date_formats = _coerce_to_list(date_formats)
        date_data = dateparser.date.parse_with_formats(date_string, date_formats, self._settings)
        return date_data.date_obj

    def parse_human_date(self, date_string: str) -> datetime.datetime | None:
        parsed_date, precision = self.parse_with_locales(date_string, [])
        if parsed_date:
            if precision == "time":
                return parsed_date
            return parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)


@lru_cache(maxsize=10)
def _get_parser(parser_kind: ParserKind | None = None, date_order: DateOrder | None = None) -> DateParser:
    return DateParser(parser_kind, date_order)


def _as_utc(date_time: datetime.datetime) -> datetime.datetime:
    return date_time.astimezone(datetime.UTC)


def _normalize(date_time: datetime.datetime) -> datetime.datetime:
    if date_time.tzinfo is not None:
        return _as_utc(date_time).replace(tzinfo=None, microsecond=0)
    if date_time.microsecond:
        return date_time.replace(microsecond=0)
    return date_time


def _suppress_warnings(func: Callable[_P, _R]) -> Callable[_P, _R]:
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        with warnings.catch_warnings(record=True):
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            return func(*args, **kwargs)

    return wrapper


@_suppress_warnings
def parse_iso(date_or_datetime: str, /) -> datetime.datetime:
    return datetime.datetime.fromisoformat(date_or_datetime)


@_suppress_warnings
def parse_human(
    date_string: str,
    /,
    parser_kind: ParserKind | None = None,
    date_order: DateOrder | None = None,
) -> datetime.datetime | None:
    parser = _get_parser(parser_kind, date_order)
    return parser.parse_human_date(date_string)


@_suppress_warnings
def parse(date_or_datetime: str, format: str | None = None, /, *, iso: bool = False) -> datetime.datetime | None:
    if not date_or_datetime:
        raise ValueError("Unable to extract date")

    if iso:
        return parse_iso(date_or_datetime)
    elif format:
        if format and (format == "%Y-%m-%d" or format.startswith("%Y-%m-%d %H:%M:%S")):
            raise ValueError("Do not use a custom format to parse iso8601 dates. Call parse_iso_date instead")
        return _get_parser().parse_possible_incomplete_date(date_or_datetime, format)
    else:
        return parse_human(date_or_datetime)


def parse_aware_iso_datetime(value: str) -> datetime.datetime | None:
    try:
        return _as_utc(parse_iso(value))
    except Exception:
        return


# Return dt obj
def parse_http(date: str, /) -> int:
    """parse rfc 2822 or an "HTTP-date" format as defined by RFC 9110"""
    date_time = email.utils.parsedate_to_datetime(date)
    return to_timestamp(date_time)


def to_timestamp(date: datetime.datetime) -> TimeStamp:
    return TimeStamp(int(date.timestamp()))


if __name__ == "__main__":
    print(parse_human("today at noon"))  # noqa: T201
    print(parse_human("today"))  # noqa: T201
