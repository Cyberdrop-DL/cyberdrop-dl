from __future__ import annotations

import base64
import dataclasses
import re
from collections.abc import Generator
from enum import IntEnum
from typing import TYPE_CHECKING, Any, NewType, TypeAlias

from bs4 import BeautifulSoup

from cyberdrop_dl.utils import css, json

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

_ChunkID: TypeAlias = str
FlightData = NewType("FlightData", str)
NextJSFlight = dict[_ChunkID, list[dict[str, Any]]]
# Map of chunk_id (hex index of the chunk) -> list of all the objects (components) created from that chunk

_match_init_push = re.compile(r"\(self\.__next_f\s?=\s?self\.__next_f\s?\|\|\s?\[\]\)\.push\((\[.+?\])\)").match


class _FlightType(IntEnum):
    BOOTSTRAP = 0
    PAYLOAD = 1
    FORM_STATE = 2
    BINARY = 3


_Push = tuple[_FlightType, str]


@dataclasses.dataclass(slots=True, order=True)
class _RawChunk:
    id: _ChunkID
    marker: str | None
    data: str


@dataclasses.dataclass(slots=True, order=True)
class _FlightChunk:
    index: int = dataclasses.field(init=False)
    id: _ChunkID
    marker: str | None
    data: str

    decoded_data: Any = dataclasses.field(init=False)  # pyright: ignore[reportAny]
    resolved: bool = dataclasses.field(init=False, default=False)

    def __post_init__(self) -> None:
        self.index = int(self.id, base=16)
        self.decoded_data = self.data


def _dedent_push(push: str) -> str:
    push = push.strip()
    if push.startswith(("{", "[")) and push.endswith(("}", "]")):
        parts = filter(None, map(str.strip, push[1:-1].partition(",")))
        push = "".join((push[0], *parts, push[-1]))
    return push


def _extract_raw_pushes(soup: BeautifulSoup) -> Generator[str]:
    push = "self.__next_f.push("
    for script in css.iselect(soup, "script:-soup-contains-own('self.__next_f')"):
        content = script.get_text(strip=True).strip()
        if m := _match_init_push(content):
            yield _dedent_push(m.group(1))
        else:
            try:
                start = content.index(push) + len(push)
            except ValueError:
                continue

            yield _dedent_push(content[start : content.rindex(")")])


def _decode_push(raw_push: str) -> _Push:
    push: list[Any] = json.loads(raw_push)  # pyright: ignore[reportAny]
    match push:
        case [_FlightType.BOOTSTRAP]:
            return _FlightType.BOOTSTRAP, "<INIT>"
        case [_FlightType.PAYLOAD | _FlightType.FORM_STATE as type_, value]:
            return _FlightType(type_), value
        case [_FlightType.BINARY, value]:
            return _FlightType.BINARY, base64.b64decode(value.encode()).decode()
        case _:
            raise RuntimeError(f"Invalid NextJS push found: {push!r}")


def _extract_flight_data(raw_pushes: Iterable[str]) -> Generator[str]:
    found_init: bool = False
    for flight_type, data in map(_decode_push, raw_pushes):
        if flight_type is _FlightType.BOOTSTRAP:
            if found_init:
                raise RuntimeError("NextJS data was initialized multiple times")
            found_init = True

        elif flight_type is _FlightType.PAYLOAD:
            if not found_init:
                raise RuntimeError("Found NextJS push without initialized array")
            yield data


def _parse_raw_chunks(flight_data: FlightData) -> Generator[_RawChunk]:
    for line in flight_data.splitlines():
        if line.startswith(":HL"):
            continue
        m = re.match("^([0-9a-f]+):(T[0-9A-Fa-f]+,|[A-SU-Z]{0,1})", line)
        assert m
        chunk_id, marker = m.groups()
        data = line[m.end() :].strip()
        if marker.startswith("T"):
            lenght = int(marker[1:-1], 16)
            data, rest = data[:lenght], FlightData(data[lenght:])
            yield _RawChunk(chunk_id, "T", data)
            if rest:
                yield from _parse_raw_chunks(rest)
        else:
            yield _RawChunk(chunk_id, marker or None, data)


def _parse_chunks(flight_data: FlightData) -> Generator[_FlightChunk]:  # noqa: C901
    chunks: dict[_ChunkID, _FlightChunk] = {}

    def revive_str(value: str) -> Any:  # noqa: PLR0911  # pyright: ignore[reportAny]
        if value[0] != "$":
            return value

        if value == "$":
            return ""

        match value[1]:
            case "$":
                return value[2:]
            case "@" | "L":
                chunk_id = value[2:]
                return revive(chunks[chunk_id])
            case "u":
                return None
            case "D":
                return value[2:]
            case "n":
                return int(value[2:])
            case _:
                return value[1:]

    def revive(value: Any) -> Any:
        if not value:
            return value

        if isinstance(value, str):
            return revive_str(value)

        if isinstance(value, list):
            for idx, obj in enumerate(value):
                value[idx] = revive(obj)

        elif isinstance(value, dict):
            for key, obj in value.items():
                value[key] = revive(obj)

        elif isinstance(value, _FlightChunk):
            initialize(value)
            return value.decoded_data

        return value

    def initialize(chunk: _FlightChunk) -> None:
        if chunk.resolved:
            return
        try:
            raw_value = json.loads(chunk.decoded_data) if isinstance(chunk.decoded_data, str) else chunk.decoded_data
        except json.JSONDecodeError:
            chunk.decoded_data = "<ERROR>"
        else:
            chunk.decoded_data = revive(raw_value)
        finally:
            chunk.resolved = True

    for chunk in _parse_raw_chunks(flight_data):
        chunks[chunk.id] = _FlightChunk(chunk.id, marker=chunk.marker or None, data=chunk.data)

    for chunk in sorted(chunks.values()):
        initialize(chunk)
        yield chunk


def extract_flight_data(soup: BeautifulSoup) -> FlightData:
    return FlightData("".join(_extract_flight_data(_extract_raw_pushes(soup))).replace('"$undefined"', "null"))


def ifind(next_flight: NextJSFlight, attr: str, *attrs: str) -> Generator[dict[str, Any]]:
    """Yield every object within `next_flight` that have the required `attrs`."""
    needed = frozenset([attr, *attrs])

    def walk(obj: object) -> Generator[dict[str, Any]]:
        if isinstance(obj, dict):
            if needed.issubset(obj):
                yield obj
            else:
                for v in obj.values():
                    yield from walk(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from walk(v)

    for ele in next_flight.values():
        yield from walk(ele)


def find(next_flight: NextJSFlight, attr: str, *attrs: str) -> dict[str, Any]:
    """Get the first object within `next_flight` that have the required `attrs`."""
    return next(ifind(next_flight, attr, *attrs))


def extract(soup: BeautifulSoup) -> NextJSFlight:
    return parse(extract_flight_data(soup))


def parse(flight_data: FlightData, /) -> NextJSFlight:
    return {chunk.id: chunk.decoded_data for chunk in _parse_chunks(flight_data)}  # pyright: ignore[reportAny]


if __name__ == "__main__":
    import sys
    from pathlib import Path

    file = Path(sys.argv[1])
    soup = BeautifulSoup(file.read_text(), "html.parser")
    flight_data = extract_flight_data(soup)
    Path("flight_data.txt").write_text(flight_data)
    data = parse(flight_data)
    Path(" flight_data_decoded.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
