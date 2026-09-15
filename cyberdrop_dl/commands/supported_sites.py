from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from rich.json import JSON
    from rich.table import Table

    from cyberdrop_dl.crawlers.crawler import CrawlerInfo


def _gen_crawlers_info() -> list[CrawlerInfo]:
    from cyberdrop_dl.crawlers import Registry

    return sorted((crawler.INFO for crawler in Registry.get_crawlers(generic=True)), key=lambda x: x.site.casefold())


def as_json() -> dict[str, dict[str, Any]]:
    return {info.site: info.__json__() for info in _gen_crawlers_info()}


def as_rich_json() -> JSON:
    from rich.json import JSON

    return JSON.from_data(as_json())


def as_rich_table() -> Table:
    from rich.table import Table
    from rich.text import Text

    table = Table(
        title=Text("cyberdrop-dl supported sites", style="green"),
        show_lines=True,
        highlight=True,
    )
    for column in ("Site", "Primary URL", "Supported Domains"):
        table.add_column(column, no_wrap=True)

    for crawler_info in _gen_crawlers_info():
        table.add_row(
            crawler_info.site,
            str(crawler_info.primary_url),
            "\n".join(crawler_info.supported_domains),
        )

    return table


def as_markdown(indent_level: int = 2) -> str:
    return "\n\n".join(_generate_md_blocks(indent_level))


def _generate_md_blocks(indent_level: int) -> Generator[str]:
    def quoted(lines: Iterable[str], quoted_char: str = "`") -> str:
        return ", ".join(f"{quoted_char}{lines}{quoted_char}" for lines in lines)

    def as_list_item(note: str) -> str:
        first, *rest = note.rstrip().splitlines()
        lines = [f"- {first}"]
        # Lines already indented (ex: a nested sub-list) are continuations of the
        # list item as-is; only un-indented lines need the 2-space list padding.
        lines.extend("" if not line else line if line.startswith(" ") else f"  {line}" for line in rest)
        return "\n".join(lines)

    for info in _gen_crawlers_info():
        url = str(info.primary_url).rstrip("/")
        lines = [
            f"{'#' * (indent_level + 1)} {info.site}",
            "",
            f"**Primary URL**: [{url}]({url})",
            "",
            f"**Supported Domains**: {quoted(info.supported_domains)}".rstrip(),
        ]

        supported_paths, notes = _get_supported_paths_and_notes(info)
        lines += ["", "**Supported Paths**:"]
        if supported_paths:
            lines.append("")
            for name, paths in supported_paths.items():
                lines.append(f"- {name}:")
                lines.extend(f"  - `{path}`" for path in paths)

        if notes:
            lines += ["", "**Notes**", ""]
            lines.extend(as_list_item(note) for note in notes)

        yield "\n".join(lines)


def _get_supported_paths_and_notes(crawler_info: CrawlerInfo) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...]]:
    supported_paths: dict[str, tuple[str, ...]] = {}
    notes: list[str] = []

    for name, paths in crawler_info.supported_paths.items():
        if isinstance(paths, str):
            paths = (paths,)

        if "direct link" in name.casefold() and paths == ("",):
            supported_paths["Direct Links"] = ()

        elif "*note*" in name.casefold():
            notes.extend(filter(None, map(str.strip, map(dedent, paths))))
        else:
            assert name not in supported_paths
            supported_paths[name] = paths

    return supported_paths, tuple(notes)
