from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from cyberdrop_dl.utils import css, dates, traversal

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from bs4.element import Tag


def _find(
    soup: Tag, keys: tuple[str, ...], validate: Mapping[str, Any] | None = None
) -> tuple[tuple[Any, ...], traversal.DictVisitor]:
    visitor = traversal.DictVisitor(keys, validate)
    json_lds = tuple(iselect(soup, tuple(visitor.target_keys)))
    return json_lds, visitor


def ifind(
    soup: Tag, *keys: str, validate: Mapping[str, Any] | None = None
) -> Iterable[tuple[traversal.Path, dict[str, Any]]]:
    json_lds, visitor = _find(soup, keys, validate)
    return traversal.traverse(json_lds, visitor)


def find(soup: Tag, *keys: str, validate: Mapping[str, Any] | None = None) -> tuple[traversal.Path, dict[str, Any]]:
    json_lds, visitor = _find(soup, keys, validate)
    try:
        return next(traversal.traverse(json_lds, visitor))
    except StopIteration:
        contains = tuple(sorted(visitor.target_keys))
        details = f" with keys {contains}" if contains else ""
        raise css.SelectorError(f"ld-json{details} not found") from None


def upload_date(soup: Tag, *keys: str, validate: Mapping[str, Any] | None = None) -> float:
    _, obj = find(soup, "uploadDate", *keys, validate=validate)
    return dates.parse_iso(obj["uploadDate"]).timestamp()


def iselect(soup: Tag, /, contains: tuple[str, ...] | str = ()) -> Iterable[Any]:
    return map(json.loads, css.iselect_text(soup, "script[type='application/ld+json']", contains))
