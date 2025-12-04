import itertools
from collections.abc import Generator, Iterable
from pathlib import Path
from typing import TypeVar

from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.scraper import _input
from cyberdrop_dl.utils.utilities import parse_url

_T = TypeVar("_T")

URLS = [
    "https://github.com/jbsparrow/CyberDropDownloader",
    "https://www.dropbox.com/scl/fo/vyuocyiqz1j93d71bdz18",
    "https://drive.google.com/file/d/1F0YBsnQRvrMbK0p9UlnyLu88kqQ0j_F6/edit",
]


def _batched(iterable: Iterable[_T], n: int) -> Generator[tuple[_T, ...]]:
    iterator = iter(iterable)
    while batch := tuple(itertools.islice(iterator, n)):
        yield batch


def _make_groups(size: int = 1):
    for idx, lines in enumerate(_batched(URLS, size), 1):
        yield f"---group {idx}"
        yield from lines


NO_GROUPS = "\n".join(URLS)
GROUPS = "\n".join(_make_groups())
GROUPED_BY_2 = "\n".join(_make_groups(2))
YARL_URLS = list(map(parse_url, URLS))


async def _read_urls_by_group(input_file: Path) -> list[tuple[tuple[str, ...], tuple[AbsoluteHttpURL, ...]]]:
    return [x async for x in _input.read_urls_by_groups(input_file)]


async def test_urls_txt_parsing(tmp_cwd: Path) -> None:
    input_file = tmp_cwd / "input.txt"
    input_file.write_text(NO_GROUPS)
    result = await _read_urls_by_group(input_file)
    assert result == [
        (
            (),
            (url,),
        )
        for url in YARL_URLS
    ]


async def test_urls_txt_groups(tmp_cwd: Path) -> None:
    input_file = tmp_cwd / "input.txt"
    input_file.write_text(GROUPS)
    result = await _read_urls_by_group(input_file)
    assert result == [
        (
            (f"group {idx}",),
            (url,),
        )
        for idx, url in enumerate(YARL_URLS, 1)
    ]


async def test_urls_txt_groups_2(tmp_cwd: Path) -> None:
    input_file = tmp_cwd / "input.txt"
    input_file.write_text(GROUPED_BY_2)
    result = await _read_urls_by_group(input_file)
    assert result == [
        (("group 1",), (YARL_URLS[0],)),
        (("group 1",), (YARL_URLS[1],)),
        (("group 2",), (YARL_URLS[2],)),
    ]


async def test_urls_txt_folder(tmp_cwd: Path) -> None:
    folder = tmp_cwd / "inputs"
    folder.mkdir()
    (folder / "input1.txt").write_text(NO_GROUPS)
    (folder / "input2.txt").write_text(GROUPS)
    result = await _read_urls_by_group(folder)

    expected_1 = [
        (
            ("input1",),
            (url,),
        )
        for url in YARL_URLS
    ]
    expected_2 = [
        (
            ("input2", f"group {idx}"),
            (url,),
        )
        for idx, url in enumerate(YARL_URLS, 1)
    ]
    assert result == expected_1 + expected_2


async def test_simple_read_urls(tmp_cwd: Path) -> None:
    input_file = tmp_cwd / "input.txt"
    input_file.write_text(NO_GROUPS)
    result = [x async for x in _input.read_urls(input_file)]
    assert result == YARL_URLS
    input_file.write_text(GROUPS)
    result = [x async for x in _input.read_urls(input_file)]
    assert result == YARL_URLS
