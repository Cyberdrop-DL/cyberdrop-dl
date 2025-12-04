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


async def read_urls(file_or_folder: Path, /) -> AsyncGenerator[tuple[str | None, str | None, list[AbsoluteHttpURL]]]:
    """Read URLs from input by their groups."""

    if await asyncio.to_thread(file_or_folder.is_dir):
        files = await asyncio.to_thread(lambda: list(file_or_folder.glob("*.txt")))
        single_file = False

    elif not await asyncio.to_thread(file_or_folder.is_file):
        yield None, None, []
        return

    else:
        files = [file_or_folder]
        single_file = True

    for file in sorted(files, key=lambda x: str(x).casefold()):
        base_group = None if single_file else file.stem
        async for file_group, urls in _read_urls(file):
            if urls:
                yield base_group, file_group, urls


async def _read_urls(input_file: Path, /) -> AsyncGenerator[tuple[str | None, list[AbsoluteHttpURL]]]:
    """Read URLs from file (html or plain text), taking groups into account and ignoring comments"""

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


def _regex_links(line: str, /) -> Generator[AbsoluteHttpURL]:
    """Regex grab the links from the URLs.txt file.

    This allows code blocks or full paragraphs to be copy and pasted into the URLs.txt.
    """

    line = line.strip()
    if line.startswith("#"):
        return

    http_urls = (url.group().replace(".md.", ".") for url in re.finditer(REGEX_LINKS, line))
    for link in http_urls:
        try:
            encoded = "%" in link
            yield AbsoluteHttpURL(link, encoded=encoded)
        except Exception as e:
            log(f"Unable to parse URL from input file: {link} {e:!r}", 40)
