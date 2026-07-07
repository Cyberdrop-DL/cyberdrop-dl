import string
from collections.abc import Generator
from typing import Any

from pydantic import AfterValidator, BeforeValidator

_FORMATER = string.Formatter()


class UnknownPlaceholder:
    """An object that always represents itself the same regardless of how it's formatted in an f-string

    Use this to prevent errors if the user supplied custom formatting for a value that the crawler was not able to scrape"""

    def __init__(self, value: str) -> None:
        self.value: str = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return self.value

    def __format__(self, format_spec: str) -> str:
        return self.value

    @staticmethod
    def make(name: str) -> "UnknownPlaceholder":
        return UnknownPlaceholder(f"UNKNOWN_{name.upper()}")


_UNTITLED = UnknownPlaceholder("Untitled")


def safe_format(format_string: str, **fields: Any) -> tuple[str, set[str]]:
    """
    Formats a string replacing any unknown keys and `None` values in the format string with an instance of `UnknownPlaceholder`

    Args:
        format_string (str): The string to be formatted.
        **kwargs: Keyword arguments for formatting.

    Returns:
        str: The formatted string with unknown keys replaced by "UNKNOWN_{KEY_NAME}".
        set[str]: collection of unknown field_names in the format string
    """

    new_kwargs = dict(fields)
    unknown_field_names = _get_unknown_field_names(format_string, set(new_kwargs.keys()))

    for field_name, value in new_kwargs.items():
        if value is None:
            if field_name.lower() == "title":
                new_kwargs[field_name] = _UNTITLED
            else:
                new_kwargs[field_name] = UnknownPlaceholder.make(field_name)

    for field_name in unknown_field_names:
        new_kwargs[field_name] = UnknownPlaceholder.make(field_name)

    return _FORMATER.vformat(format_string, (), new_kwargs), unknown_field_names


def validate_format(format_string: str, valid_keys: set[str]) -> None:
    msg = "invalid format string. "
    for _, field_name, _, _ in _FORMATER.parse(format_string):
        if field_name is not None:
            if field_name.isdigit() or field_name == "":
                msg += "Format strings with positional arguments are not valid config options"
                raise ValueError(msg)
            if not field_name.isidentifier():
                msg += "Operations within a format string are not supported"
                raise ValueError(msg)

    if unknown_field_names := _get_unknown_field_names(format_string, valid_keys):
        msg += " ".join(
            (
                f"{tuple(sorted(unknown_field_names))}",
                f"{'is not a valid field' if len(unknown_field_names) == 1 else 'are not valid fields'}",
                f"for this option. \n\n  Valid fields: {sorted(valid_keys)}",
            )
        )
        raise ValueError(msg)


def _get_field_names(format_string: str) -> Generator[str]:
    for _literal_text, field_name, _fmt_spec, _conversion in _FORMATER.parse(format_string):
        if field_name and not field_name.isdigit():  # Ignore positional args and empty fields
            yield field_name


def _get_unknown_field_names(format_string: str, valid_keys: set[str]) -> set[str]:
    field_names = set(_get_field_names(format_string))
    return field_names - valid_keys


def pre_validator(*, to_upper: bool = False, to_lower: bool = False, strip: bool = False) -> BeforeValidator:
    def coerce[T](value: T | str) -> T | str:
        if not isinstance(value, str):
            return value
        if to_upper:
            value = value.upper()
        if to_lower:
            value = value.lower()
        if strip:
            value = value.strip()
        return value

    return BeforeValidator(coerce)


def format_validator(valid_keys: set[str]) -> AfterValidator:
    def check[T](value: T) -> T:
        if isinstance(value, str):
            validate_format(value, valid_keys)
        return value

    return AfterValidator(check)
