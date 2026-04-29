from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from collections.abc import Generator

    from cyberdrop_dl.crawlers.crawler import CrawlerInfo


def _gen_crawlers_info() -> Generator[CrawlerInfo]:
    from cyberdrop_dl.crawlers.crawler import Registry

    Registry.import_all()

    crawlers = Registry.generic | Registry.concrete
    infos = (crawler.INFO for crawler in crawlers)
    yield from sorted(infos, key=lambda x: x.site.casefold())


def as_rich_table() -> Table:
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
            str(crawler_info.primary_url).rstrip("/"),
            "\n".join(crawler_info.supported_domains),
        )

    return table


def as_markdown(indent_level: int = 2) -> str:
    indent = "#" * indent_level

    def pad(line: str):
        if line.startswith("#"):
            return indent + line
        return line

    return "\n".join(map(pad, _generate_md_rows()))


def _generate_md_rows() -> Generator[str]:
    for info in _gen_crawlers_info():
        yield f"# {info.site}\n"
        yield f"Primary URL: {str(info.primary_url).rstrip('/')}\n"
        yield f"Supported Domains: {', '.join(info.supported_domains)}\n"

        supported_paths, notes = _get_supported_paths_and_notes(info)
        yield "## Supported paths"
        for name, paths in supported_paths.items():
            all_paths = ",".join(f"`{path}`" for path in paths)
            yield f"- {name}: {all_paths}"

        if notes:
            yield "\n## Notes"
            for note in notes:
                yield f"- {note}"

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
            notes.extend(paths)
        else:
            assert name not in supported_paths
            supported_paths[name] = paths

    return supported_paths, tuple(notes)
