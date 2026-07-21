import dataclasses

import pytest

from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import dataclass
from cyberdrop_dl.utils._url import parse_http_url


@dataclasses.dataclass
class A:
    b: int
    c: str


def test_default_deserialize() -> None:
    result = dataclass.deserialize(A, {"a": 1, "b": 2, "c": "string"})
    assert type(result) is A
    assert result.b == 2
    assert result.c == "string"


def test_deserialize_w_overrides() -> None:
    result = dataclass.deserialize(A, {"a": 1, "b": 2}, c="string")
    assert result.b == 2
    assert result.c == "string"
    result = dataclass.deserialize(A, {"a": 1, "b": 2, "c": "string"}, c="other string")
    assert result.c == "other string"


def test_deserialize_w_aliases() -> None:
    data = {"a": 1, "b": 2, "custom_key": "string"}

    with pytest.raises(TypeError):
        dataclass.deserialize(A, data)
    deserialize = dataclass.Deserializer({"c": "custom_key"})
    result = deserialize(A, data)
    assert result.b == 2
    assert result.c == "string"


def test_deserialize_w_converter() -> None:

    @dataclasses.dataclass
    class B:
        a: int
        b: int
        c: AbsoluteHttpURL

    data = {"a": 1, "b": "2", "c": "https://example.com"}

    deserialize = dataclass.Deserializer(converters={"b": int, "c": parse_http_url})
    result = deserialize(B, data)
    assert type(result) is B
    assert result.a == 1
    assert result.b == 2
    assert result.c == AbsoluteHttpURL("https://example.com")

    with pytest.raises(ValueError, match="Relative URL with no known origin"):
        deserialize(B, {"a": 1, "b": "2", "c": "not and url"})
