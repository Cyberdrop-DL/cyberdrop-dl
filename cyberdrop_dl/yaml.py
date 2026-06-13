from __future__ import annotations

from datetime import date, timedelta
from enum import Enum
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Any

import yaml
from yarl import URL

from cyberdrop_dl.exceptions import InvalidYamlError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pydantic import BaseModel
    from yaml.nodes import ScalarNode


def _str(dumper: yaml.Dumper, value: object) -> ScalarNode:
    return dumper.represent_str(str(value))


def _enum(dumper: yaml.Dumper, value: Enum) -> ScalarNode:
    return dumper.represent_str(value.name)


def _date(dumper: yaml.Dumper, value: date) -> ScalarNode:
    return dumper.represent_str(value.isoformat())


def _list(dumper: yaml.Dumper, value: Iterable[Any]):
    return dumper.represent_list(value)


yaml.add_multi_representer(PurePath, _str)
yaml.add_multi_representer(Enum, _enum)
yaml.add_multi_representer(date, _date)
yaml.add_representer(tuple, _list)
yaml.add_representer(timedelta, _str)
yaml.add_representer(URL, _str)


def save(file: Path, /, data: BaseModel | dict[str, Any]) -> None:
    """Saves a dict to a yaml file."""
    if not isinstance(data, dict):
        data = data.model_dump()

    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("w", encoding="utf8") as file_io:
        yaml.dump(data, file_io, default_flow_style=False)


def load(file: Path, /) -> dict[str, Any]:
    try:
        with file.open("r", encoding="utf8") as file_io:
            return yaml.safe_load(file_io) or {}

    except yaml.YAMLError as e:
        raise InvalidYamlError(file, e) from e
