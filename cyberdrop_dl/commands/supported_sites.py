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

    return sorted(crawler.INFO for crawler in Registry.get_crawlers(generic=True))


def _as_json() -> dict[str, dict[str, Any]]:
    return {info.site: info.__json__() for info in _gen_crawlers_info()}


def as_json() -> JSON:

    from rich.json import JSON

    return JSON.from_data(_as_json())


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
    indent = "#" * indent_level

    def pad(line: str) -> str:
        if line.startswith("#"):
            return indent + line
        return line

    return "\n".join(map(pad, _generate_md_rows()))


def _generate_md_rows() -> Generator[str]:
    def quoted(lines: Iterable[str], quoted_char: str = "`") -> str:
        return ", ".join(f"{quoted_char}{lines}{quoted_char}" for lines in lines)

    for info in _gen_crawlers_info():
        url = str(info.primary_url).rstrip("/")
        yield f"# {info.site}\n"
        yield f"**Primary URL**: [{url}]({url})\n"
        yield f"**Supported Domains**: {quoted(info.supported_domains)}".rstrip() + "\n"

        supported_paths, notes = _get_supported_paths_and_notes(info)
        yield "**Supported Paths**:\n"
        for name, paths in supported_paths.items():
            yield f"- {name}:"
            for path in paths:
                yield f"  - `{path}`"

        if notes:
            yield "\n"
            yield "**Notes**\n"
            for note in notes:
                yield f"- {note.rstrip()}"

        yield "\n"


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
