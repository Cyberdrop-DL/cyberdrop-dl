from __future__ import annotations

import base64
import contextlib
import dataclasses
import datetime
import enum
import functools
import json
import json.decoder
import json.scanner
import re
import time
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple, Protocol, Self, TypeGuard

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable
    from pathlib import Path

    from pydantic import BaseModel


_scanstring: Callable[..., tuple[str, int]] = json.decoder.scanstring  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
_py_make_scanner: Callable[..., tuple[Any, int]] = json.scanner.py_make_scanner  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]

_encoders: dict[tuple[bool, int | None], LenientJSONEncoder] = {}
_REPLACE_QUOTES_PAIRS = (
    ("{'", '{"'),
    ("'}", '"}'),
    ("['", '["'),
    ("']", '"]'),
    (",'", ',"'),
    ("':", '":'),
    (", '", ', "'),
    ("' :", '" :'),
    ("',", '",'),
    (": '", ': "'),
)


class _DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, dataclasses.Field[Any]]]


def default(obj: object, /) -> Any:  # noqa: PLR0911
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, set):
        return sorted(obj)
    if callable(serialize := getattr(obj, "__json__", None)):
        return serialize()
    if _is_namedtuple_instance(obj):
        return obj._asdict()
    if _is_dataclass_instance(obj):
        return dataclasses.asdict(obj)
    if _is_pydantic_instance(obj):
        return obj.model_dump()
    return str(obj)


class LenientJSONEncoder(json.JSONEncoder):
    def __init__(self, *, sort_keys: bool = False, indent: int | None = None) -> None:
        super().__init__(check_circular=False, ensure_ascii=False, sort_keys=sort_keys, indent=indent, default=default)


class JSDecoder(json.JSONDecoder):
    """Custom decoder that tries to transforms javascript objects into valid json

    It can only handle simple js objects"""

    def __init__(self) -> None:
        super().__init__()
        self.parse_string = _parse_js_string
        self.scan_once = _py_make_scanner(self)


JSONDecodeError = json.JSONDecodeError


@contextlib.contextmanager
def _verbose_context() -> Generator[None]:
    try:
        yield
    except json.JSONDecodeError as e:
        sub_string = e.doc[e.pos - 10 : e.pos + 10]
        msg = f"{e.msg} at around '{sub_string}', char: '{e.doc[e.pos]}'"
        raise json.JSONDecodeError(msg, e.doc, e.pos) from None


def _verbose[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        with _verbose_context():
            return func(*args, **kwargs)

    return wrapper


def _get_encoder(*, sort_keys: bool = False, indent: int | None = None) -> LenientJSONEncoder:
    key = sort_keys, indent
    encoder = _encoders.get(key)
    if encoder is None:
        encoder = _encoders[key] = LenientJSONEncoder(sort_keys=sort_keys, indent=indent)
    return encoder


def _parse_js_string(*args: Any, **kwargs: Any) -> tuple[Any, int]:
    string, end = _scanstring(*args, **kwargs)
    for quote in ("'", '"'):
        if len(string) > 2 and string.startswith(quote) and string.endswith(quote):
            string = string[1:-1]
    return _literal_value(string), end


def _literal_value(string: str) -> Any:
    if string.isdigit():
        return int(string)
    if string == "undefined":
        return None
    if string in {"true", "!0"}:
        return True
    if string in {"false", "!1"}:
        return False
    return string


def _is_namedtuple_instance(obj: object, /) -> TypeGuard[NamedTuple]:
    return isinstance(obj, tuple) and hasattr(obj, "_asdict") and hasattr(obj, "_fields")


def _is_dataclass_instance(obj: object, /) -> TypeGuard[_DataclassInstance]:
    return dataclasses.is_dataclass(obj) and not isinstance(obj, type)


def _is_pydantic_instance(obj: object, /) -> TypeGuard[BaseModel]:
    return hasattr(obj, "model_dump") and not isinstance(obj, type)


def dumps(obj: object, /, *, sort_keys: bool = False, indent: int | None = None, **_: object) -> Any:
    encoder = _get_encoder(sort_keys=sort_keys, indent=indent)
    return encoder.encode(obj)


def dump_jsonl(data: Iterable[dict[str, Any]], /, file: Path) -> None:
    with file.open(mode="a", encoding="utf8") as f:
        for item in data:
            f.writelines(_DEFAULT_ENCODER.iterencode(item))
            f.write("\n")


_JS_DECODER = JSDecoder()
_DEFAULT_ENCODER = _get_encoder()
loads = _verbose(json.loads)


@_verbose
def load_js_obj(string: str, /) -> Any:
    """Parses a string representation of a JavaScript object into a Python object.

    It can handle JavaScript object strings that may not be valid JSON"""

    string = string.replace("\t", "").replace("\n", "").strip()
    # Remove tailing comma
    string = string[:-1].strip().removesuffix(",") + string[-1]
    # Make it valid json by replacing single quotes with double quotes
    # we can't just replace every single ' with " because it will brake with english words like: it's
    for old, new in _REPLACE_QUOTES_PAIRS:
        string = string.replace(old, new)
    string = re.sub(r"\s\b(?!http)(\w+)\s?:", r' "\1" : ', string)  # wrap keys without quotes with double quotes
    return _JS_DECODER.decode(string)


@dataclasses.dataclass(slots=True, frozen=True)
class JSONWebToken:
    # https://www.rfc-editor.org/rfc/rfc7519.html
    alg: str
    headers: dict[str, str]
    payload: dict[str, Any]
    signature: str
    encoded: str

    @classmethod
    def decode(cls, jwt: str, /) -> Self:
        if not looks_like_jwt(jwt):
            raise ValueError("Not a valid JSON Web Token", jwt)
        b64_headers, b64_payload, b64_signature = jwt.split(".")
        headers = cls._decode(b64_headers)
        return cls(headers["alg"], headers, cls._decode(b64_payload), b64_signature, jwt)

    @classmethod
    def _decode(cls, payload: str, /) -> dict[str, Any]:
        return loads(base64.urlsafe_b64decode(f"{payload}==="))

    def is_expired(self, threshold: int = 0) -> bool:
        """Checks if the token has expired or is about to expire.

        threshold is the time in seconds before the token's expiration to consider it as expired.
        """
        expires: int | None = self.payload.get("exp")
        if expires:
            return (expires - time.time()) < threshold
        return False

    def __str__(self) -> str:
        return self.encoded


def looks_like_jwt(string: str) -> bool:
    return string.startswith("eyJ") and string.count(".") == 2


def jwt_decode(jwt: str) -> dict[str, Any]:
    return JSONWebToken.decode(jwt).payload
