from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Sequence

type Row = list[str] | tuple[str, ...]
type _RowLike = Iterable[str]


def markdown_table(headers: Sequence[str], *rows: Row) -> str:
    if len(headers) == 0:
        raise ValueError("At least 1 header is required")

    if len(rows) == 0:
        raise ValueError("At least 1 row is required")

    _sanity_check(headers)
    return "\n".join(_md_table_lines([headers, *rows]))


def _md_table_lines(rows: Sequence[_RowLike]) -> Generator[str]:
    column_widths = _get_columns_widths(rows)

    def justify(row: _RowLike) -> _RowLike:
        for value, width in zip(row, column_widths, strict=True):
            yield value.strip().ljust(width)

    lines = (_compose_md_line(justify(row)) for row in rows)
    yield next(lines)
    yield _compose_md_line("-" * w for w in column_widths)
    yield from lines


def _compose_md_line(row: _RowLike) -> str:
    return "| " + " | ".join(value.replace("|", r"\|") for value in row) + " |"


def _sanity_check[T: _RowLike](row: T) -> T:
    if isinstance(row, str):
        raise TypeError("strings are not valid rows", row)
    return row


def _get_columns_widths(rows: Sequence[_RowLike]) -> tuple[int, ...]:
    row_widths = (map(len, _sanity_check(row)) for row in rows if row)
    return tuple(map(max, zip(*row_widths, strict=True)))


if __name__ == "__main__":
    print(  # noqa: T201
        markdown_table(
            ["col 1", "col 2", "      col 3"],
            ["val 1", "val 2 long", "val 3"],
        )
    )
