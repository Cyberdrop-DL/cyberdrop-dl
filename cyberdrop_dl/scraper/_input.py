from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

import aiofiles

from cyberdrop_dl.constants import REGEX_LINKS
from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils.logger import log

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator
    from pathlib import Path


async def read_urls(input_file: Path, /) -> AsyncGenerator[tuple[str | None, str | None, list[AbsoluteHttpURL]]]:
    """Split URLs from input file by their groups."""

    if await asyncio.to_thread(input_file.is_dir):
        files = input_file.glob("*.txt")
        single_file = False

    elif not await asyncio.to_thread(input_file.is_file):
        yield ("", [])
        return

    else:
        files = [input_file]
        single_file = True

    for file in files:
        base_group = None if single_file else file.name
        async for x, y in _parse_input_file(file):
            yield base_group, x, y


async def _parse_input_file(input_file: Path) -> AsyncGenerator[tuple[str | None, list[AbsoluteHttpURL]]]:
    """Split URLs from input file by their groups."""

    block_quote = False
    current_group_name: str | None = None
    async with aiofiles.open(input_file, encoding="utf8") as f:
        async for line in f:
            if line.startswith(("---", "===")):  # New group begins here
                current_group_name = line.replace("---", "").replace("===", "").strip()

            if current_group_name:
                yield (current_group_name, list(_regex_links(line)))
                continue

            block_quote = not block_quote if line == "#\n" else block_quote
            if not block_quote:
                yield None, list(_regex_links(line))


def _regex_links(line: str) -> Generator[AbsoluteHttpURL]:
    """Regex grab the links from the URLs.txt file.

    This allows code blocks or full paragraphs to be copy and pasted into the URLs.txt.
    """

    line = line.strip()
    if line.startswith("#"):
        return

    http_urls = (x.group().replace(".md.", ".") for x in re.finditer(REGEX_LINKS, line))
    for link in http_urls:
        try:
            encoded = "%" in link
            yield AbsoluteHttpURL(link, encoded=encoded)
        except Exception as e:
            log(f"Unable to parse URL from input file: {link} {e:!r}", 40)
