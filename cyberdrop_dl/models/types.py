from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import (
    AfterValidator,
    BeforeValidator,
    ByteSize,
    HttpUrl,
    NonNegativeInt,
    PlainSerializer,
    PlainValidator,
    StringConstraints,
)

from cyberdrop_dl.models.validators import (
    bytesize_to_str,
    change_path_suffix,
    falsy_as_list,
    falsy_as_none,
    to_yarl_url,
)
from cyberdrop_dl.url_objects import AbsoluteHttpURL

# ~~~~~ Strings ~~~~~~~
NonEmptyStr = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
NonEmptyStrOrNone = Annotated[NonEmptyStr | None, BeforeValidator(falsy_as_none)]
ListNonEmptyStr = Annotated[list[NonEmptyStr], BeforeValidator(falsy_as_list)]


# ~~~~~ Paths ~~~~~~~
PathOrNone = Annotated[Path | None, BeforeValidator(falsy_as_none)]
LogPath = Annotated[Path, AfterValidator(change_path_suffix(".csv"))]
MainLogPath = Annotated[LogPath, AfterValidator(change_path_suffix(".log"))]

# URL with pydantic.HttpUrl validation (must be absolute, must be http/https, detailed validation error).
# In type hints it's a yarl.URL. After validation the result is parsed with `parse_url` so this is also a yarl.URL at runtime
# Only use for config validation. To parse URLs internally while scraping, call `parse_url` directly
HttpURL = Annotated[AbsoluteHttpURL, PlainValidator(lambda x: to_yarl_url(HttpUrl(str(x))))]

# ~~~~~ Others ~~~~~~~
ByteSizeSerilized = Annotated[ByteSize, PlainSerializer(bytesize_to_str, return_type=str)]
ListNonNegativeInt = Annotated[list[NonNegativeInt], BeforeValidator(falsy_as_list)]
ListPydanticURL = Annotated[list[HttpURL], BeforeValidator(falsy_as_list)]
