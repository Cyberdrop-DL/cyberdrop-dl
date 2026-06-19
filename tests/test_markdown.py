from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from cyberdrop_dl.utils import markdown

if TYPE_CHECKING:
    from collections.abc import Sequence


def test_empty_headers_raise_value_error() -> None:
    with pytest.raises(ValueError, match="header"):
        _ = markdown.markdown_table((), ("a", "b"))


def test_empty_rows_raise_value_error() -> None:
    with pytest.raises(ValueError, match="row"):
        _ = markdown.markdown_table(("a", "b"))


@pytest.mark.parametrize(
    ("headers", "rows"),
    [
        ("headers", [("a", "b")]),
        (("a", "b"), ["row1", "row2"]),
    ],
)
def test_strings_are_not_valid_rows(headers: Sequence[str], rows: tuple[markdown.Row]) -> None:
    with pytest.raises(TypeError, match="rows"):
        _ = markdown.markdown_table(headers, *rows)


def test_get_columns_widths() -> None:
    rows = ["a", "b", "c"], ["aa", "b", "c"], ["a", "bbbb", "c"]
    assert markdown._get_columns_widths(rows) == (2, 4, 1)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (("1", "2", "3"), "| 1 | 2 | 3 |"),
        (("a", "example", "and", "another"), "| a | example | and | another |"),
        (("name",), "| name |"),
        (("a|b", "c", "name|"), r"| a\|b | c | name\| |"),
    ],
)
def test_compose_md_line(values: tuple[str, ...], expected: str) -> None:
    assert markdown._compose_md_line(values) == expected


def test_md_table_lines() -> None:
    rows = [
        ("Index", "Name", "Description", "Price"),
        ("1", "Compact Printer", "Air Advanced | Digital", "100.0"),
        ("2", "Tablet", "Discussion loss politics free one thousand", "22.3"),
        ("3", "Smart Blender Cooker", "discontinued", "0"),
    ]
    md = list(markdown._md_table_lines(rows))
    expected = [
        "| Index | Name                 | Description                                | Price |",
        "| ----- | -------------------- | ------------------------------------------ | ----- |",
        "| 1     | Compact Printer      | Air Advanced \\| Digital                     | 100.0 |",
        "| 2     | Tablet               | Discussion loss politics free one thousand | 22.3  |",
        "| 3     | Smart Blender Cooker | discontinued                               | 0     |",
    ]
    for line, expected_line in zip(md, expected, strict=True):
        assert line == expected_line
