from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import rich
from rich.table import Table

from cyberdrop_dl.progress import hyperlink

if TYPE_CHECKING:
    from cyberdrop_dl.crawlers.crawler import Crawler


def find_subclasses_of(domain: str):
    from cyberdrop_dl.crawlers import Registry

    crawlers = tuple(Registry.get_crawlers(generic=True, abc=True))

    if domain.endswith("Crawler"):
        target = next(c for c in crawlers if c.__name__ == domain)
    else:
        target = next(c for c in crawlers if getattr(c, "DOMAIN", None) == domain)

    return dict(sorted((c.__name__, c) for c in crawlers if issubclass(c, target) and c is not target))


def module_path(cls: type):
    spec = importlib.util.find_spec(cls.__module__)
    assert spec
    assert spec.origin
    return hyperlink(Path(spec.origin))


def make_table(subclasses: dict[str, type[Crawler]]):

    table = Table(
        show_lines=True,
        highlight=True,
    )
    for column in ("name", "URL", "path"):
        table.add_column(column, no_wrap=True)

    for name, crawler in subclasses.items():
        table.add_row(name, str(getattr(crawler, "PRIMARY_URL", None)), module_path(crawler))

    return table


if __name__ == "__main__":
    domain = sys.argv[1]
    subclasses = find_subclasses_of(domain)
    table = make_table(subclasses)
    rich.print(table)
