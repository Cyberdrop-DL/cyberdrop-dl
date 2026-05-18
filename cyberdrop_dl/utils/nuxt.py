from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from cyberdrop_dl.utils import css

if TYPE_CHECKING:
    from collections.abc import Generator

    from bs4.element import Tag


logger = logging.getLogger(__name__)


def extract(soup: Tag) -> list[Any]:
    return json.loads(css.select_text(soup, "script#__NUXT_DATA__"))


def find(nuxt_data: list[Any], attribute: str, *attributes: str) -> dict[str, Any]:
    """Parses a single object from a NUXT rich JSON payload response (__NUXT_DATA__)

    It iterates over each object until it finds an object with the desired attributes"""
    if obj := next(ifind(nuxt_data, attribute, *attributes), None):
        return obj
    raise css.SelectorError(f"Unable to find object with {attributes = } in NUXT_DATA")


def ifind(nuxt_data: list[Any], attribute: str, *attributes: str) -> Generator[dict[str, Any]]:
    """
    Iterates over each object from a NUXT rich JSON payload response (__NUXT_DATA__)

    It bypasses the devalue parsing logic by ignoring objects without the desired attributes

    https://github.com/nuxt/nuxt/discussions/20879
    """
    attributes = attribute, *attributes
    objects = (obj for obj in nuxt_data if isinstance(obj, dict) and all(key in obj for key in attributes))
    for obj in objects:
        try:
            index: int = obj[attribute]
            index_map: dict[str, int] = nuxt_data[index]
            if not isinstance(index_map, dict):
                raise TypeError

        except (LookupError, TypeError):
            index_map = obj

        yield _parse_obj(nuxt_data, index_map)


def _parse_obj(nuxt_data: list[Any], index_map: dict[str, int]) -> dict[str, Any]:
    def hydrate(value: Any) -> Any:
        if isinstance(value, list):
            match value:
                case ["BigInt", val]:
                    return int(val)
                case ["Date" | "Object" | "RegExp", val, *_]:
                    return val
                case ["Set", *values]:
                    return [hydrate(nuxt_data[idx]) for idx in values]
                case ["Map", *values]:
                    return hydrate(dict(zip(*(iter(values),) * 2, strict=True)))
                case ["ShallowRef" | "ShallowReactive" | "Ref" | "Reactive" | "NuxtError", idx]:
                    return hydrate(nuxt_data[idx])
                case [str(name), *rest]:
                    logger.warning(f"Unable to parse custom object {name} {rest}")
                    return None
                case _:
                    return [hydrate(nuxt_data[idx]) for idx in value]

        if isinstance(value, dict):
            return _parse_obj(nuxt_data, value)

        return value

    return {name: hydrate(nuxt_data[idx]) for name, idx in index_map.items()}
