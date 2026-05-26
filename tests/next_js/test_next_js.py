from pathlib import Path

from bs4 import BeautifulSoup

from cyberdrop_dl.utils import next_js

TEST_HTML = (Path(__file__).parent / "nextjsv13.html").read_text()
soup = BeautifulSoup(TEST_HTML, "html.parser")


def test_extract_raw_pushes() -> None:
    result = list(next_js._extract_raw_pushes(soup))
    assert len(result) == 26
