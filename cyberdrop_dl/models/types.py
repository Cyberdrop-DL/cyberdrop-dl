import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import ByteSize, Field, PlainSerializer, StringConstraints, WithJsonSchema
from pydantic.functional_validators import AfterValidator, BeforeValidator, PlainValidator

from cyberdrop_dl.url_objects import AbsoluteHttpURL

from .validators import bytesize_to_str, change_path_suffix, falsy_as_none, strings, to_timedelta, to_yarl_url

type LogLevel = Annotated[
    Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"], strings.pre_validator(to_upper=True, strip=True)
]
type NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
type FormatStr = Annotated[str, StringConstraints(min_length=1)]
type CSVPath = Annotated[Path, AfterValidator(change_path_suffix(".csv"))]
type LogPath = Annotated[Path, AfterValidator(change_path_suffix(".log"))]
type ByteSizeSerilized = Annotated[ByteSize, PlainSerializer(bytesize_to_str, return_type=str, when_used="json")]
type FalsyAsNone[T] = Annotated[T | None, BeforeValidator(falsy_as_none)]
type Timedelta = Annotated[
    datetime.timedelta,
    BeforeValidator(to_timedelta),
    Field(ge=datetime.timedelta(seconds=0)),
    PlainSerializer(
        str, return_type=str, when_used="json"
    ),  # Serialize as str to save it as sexageximal (hh:mm:ss) instead of pydantic's ISO duration (PT1H5M26S)
]


# Only use this for config validation. To parse URLs internally while scraping, call `parse_url` directly
type HttpURL = Annotated[
    AbsoluteHttpURL,
    PlainValidator(to_yarl_url, json_schema_input_type=str),
    WithJsonSchema({"type": "string", "format": "uri"}),
]
