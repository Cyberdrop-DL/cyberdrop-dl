from pathlib import Path

from bs4 import BeautifulSoup

from cyberdrop_dl.utils import next_js

TEST_HTML = (Path(__file__).parent / "nextjsv13.html").read_text()
soup = BeautifulSoup(TEST_HTML, "html.parser")


def test_extract_raw_pushes() -> None:
    pushes = list(next_js._extract_raw_pushes(soup))
    assert len(pushes) == 26
    for push in pushes:
        chunk_id, _, data = push[1:-1].partition(",")
        assert chunk_id == chunk_id.strip()
        assert data == data.strip()


def test_decode_push(push: str, extecte) -> None: ...
