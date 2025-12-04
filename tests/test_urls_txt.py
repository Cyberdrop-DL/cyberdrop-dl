from pathlib import Path

from cyberdrop_dl.data_structures.url_objects import AbsoluteHttpURL
from cyberdrop_dl.scraper import _input
from cyberdrop_dl.utils.utilities import parse_url

URLS = [
    "https://github.com/jbsparrow/CyberDropDownloader",
    "https://www.dropbox.com/scl/fo/vyuocyiqz1j93d71bdz18",
    "https://drive.google.com/file/d/1F0YBsnQRvrMbK0p9UlnyLu88kqQ0j_F6/edit",
]


def _make_groups():
    for idx, line in enumerate(URLS, 1):
        yield f"---group {idx}"
        yield line


NO_GROUPS = "\n".join(URLS)
GROUPS = "\n".join(_make_groups())
YARL_URLS = list(map(parse_url, URLS))


async def _read_urls(input_file: Path) -> list[tuple[str | None, str | None, list[AbsoluteHttpURL]]]:
    return [x async for x in _input.read_urls(input_file)]


async def test_urls_txt_parsing(tmp_cwd: Path) -> None:
    input_file = tmp_cwd / "input.txt"
    input_file.write_text(NO_GROUPS)
    result = await _read_urls(input_file)
    assert result == [(None, None, [url]) for url in YARL_URLS]


async def test_urls_txt_groups(tmp_cwd: Path) -> None:
    input_file = tmp_cwd / "input.txt"
    input_file.write_text(GROUPS)
    result = await _read_urls(input_file)
    assert result == [(None, f"group {idx}", [url]) for idx, url in enumerate(YARL_URLS, 1)]


async def test_urls_txt_folder(tmp_cwd: Path) -> None:
    folder = tmp_cwd / "inputs"
    folder.mkdir()
    (folder / "input1.txt").write_text(NO_GROUPS)
    (folder / "input2.txt").write_text(GROUPS)
    result = await _read_urls(folder)

    expected_1 = [("input1", None, [url]) for url in YARL_URLS]
    expected_2 = [("input2", f"group {idx}", [url]) for idx, url in enumerate(YARL_URLS, 1)]
    assert result == expected_1 + expected_2
