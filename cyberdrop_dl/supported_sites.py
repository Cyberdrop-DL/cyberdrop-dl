from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable

    from cyberdrop_dl.crawlers.crawler import CrawlerInfo

_COLUMNS = ("Site", "Primary URL", "Supported Domains", "Supported Paths")


def get_crawlers_info_as_rich_table() -> Table:
    table = Table(
        title=Text("cyberdrop-dl supported sites", style="green"),
        show_lines=True,
        highlight=True,
    )
    for column in _COLUMNS[0:3]:
        table.add_column(column, no_wrap=True)

    for row_values in _gen_crawlers_info_rows():
        table.add_row(*row_values[:3])

    return table


def _gen_crawlers_info_rows() -> Generator[tuple[str, ...]]:
    from cyberdrop_dl.crawlers.crawler import Registry

    Registry.import_all()

    crawlers = Registry.generic | Registry.concrete
    infos = (crawler.INFO for crawler in crawlers)
    for info in sorted(infos, key=lambda x: x.site.casefold()):
        yield _get_row_values(info)


def get_crawlers_info_as_markdown_table() -> str:
    from py_markdown_table.markdown_table import markdown_table

    rows = list(_make_html_rows())
    table = markdown_table(rows).set_params("markdown", padding_width=10, padding_weight="centerright", quote=False)
    return table.get_markdown()


def _make_html_rows() -> Generator[dict[str, str]]:
    for row in _gen_crawlers_info_rows():
        values = (value.replace("\n", "<br>") for value in row)
        yield dict(zip(_COLUMNS, values, strict=True))


def _get_row_values(crawler_info: CrawlerInfo) -> tuple[str, ...]:
    supported_paths, notes = _get_supported_paths_and_notes(crawler_info)
    if notes:
        supported_paths = f"{supported_paths}\n\n**NOTES**\n{notes}"
    supported_domains = "\n".join(crawler_info.supported_domains)
    return crawler_info.site, str(crawler_info.primary_url).rstrip("/"), supported_domains, supported_paths


def _get_supported_paths_and_notes(crawler_info: CrawlerInfo) -> tuple[str, str]:
    supported_paths: list[str] = []
    notes: list[str] = []

    def join(paths: Iterable[str], *, quote_char: str = "`") -> str:
        return "\n".join(f" - {quote_char}{p}{quote_char}" for p in paths)

    for name, paths in crawler_info.supported_paths.items():
        if isinstance(paths, str):
            paths = (paths,)

        if "direct link" in name.casefold() and paths == ("",):
            supported_paths.append("Direct Links")

        elif "*note*" in name.casefold():
            notes.append(join(paths, quote_char=""))
        else:
            supported_paths.append(f"{name}: \n{join(paths)}")

    return "\n".join(supported_paths), "\n".join(notes)
