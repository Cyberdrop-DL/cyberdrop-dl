import datetime
from pathlib import Path
from typing import Annotated, ClassVar, Literal

from pydantic import (
    AfterValidator,
    AnyUrl,
    BeforeValidator,
    ByteSize,
    Field,
    PlainSerializer,
    PlainValidator,
    StringConstraints,
    UrlConstraints,
    WithJsonSchema,
)

from cyberdrop_dl.url_objects import AbsoluteHttpURL

from .validators import (
    bytesize_to_str,
    change_path_suffix,
    falsy_as_none,
    falsy_as_tuple,
    remove_duplicates,
    strings,
    to_timedelta,
    to_yarl_url,
)

type LogLevel = Annotated[
    Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], strings.pre_validator(to_upper=True, strip=True)
]
type NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
type FormatStr = Annotated[str, StringConstraints(min_length=1)]
type CSVPath = Annotated[Path, AfterValidator(change_path_suffix(".csv"))]
type LogPath = Annotated[Path, AfterValidator(change_path_suffix(".log"))]
type ByteSizeSerilized = Annotated[ByteSize, PlainSerializer(bytesize_to_str, return_type=str, when_used="json")]
type FalsyAsTuple[T] = Annotated[tuple[T, ...], BeforeValidator(falsy_as_tuple)]
type FalsyAsNone[T] = Annotated[T | None, BeforeValidator(falsy_as_none)]
type Timedelta = Annotated[
    datetime.timedelta,
    BeforeValidator(to_timedelta),
    Field(ge=datetime.timedelta(seconds=0)),
    PlainSerializer(
        str, return_type=str, when_used="json"
    ),  # Serialize as str to save it as sexageximal (hh:mm:ss) instead of pydantic's ISO duration (PT1H5M26S)
]
type RemoveDuplicates[T: tuple[str, ...]] = Annotated[T, AfterValidator(remove_duplicates)]


class _HttpURL(AnyUrl):
    _constraints: ClassVar[UrlConstraints] = UrlConstraints(
        max_length=2083,
        allowed_schemes=["http", "https"],
        host_required=True,
    )


# Only use this for config validation. To parse URLs internally while scraping, call `parse_url` directly
type HttpURL = Annotated[
    AbsoluteHttpURL,
    PlainValidator(
        lambda x: to_yarl_url(_HttpURL(str(x))),
        json_schema_input_type=str,
    ),
    WithJsonSchema({"type": "string", "format": "uri"}),
]
