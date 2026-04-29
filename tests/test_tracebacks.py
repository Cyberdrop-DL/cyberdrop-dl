from bs4 import BeautifulSoup
from rich import pretty
from rich.traceback import Traceback

from cyberdrop_dl import tracebacks

soup = BeautifulSoup("".join(f"{i}" for i in range(500)), "html.parser")


def test_pretty_truncates_bs4() -> None:
    output = pretty.traverse(soup).value_repr

    assert len(output) > 500
    tracebacks.patch()

    output = pretty.traverse(soup).value_repr
    assert 100 < len(output) < 200


def test_bs4_are_truncated_on_tracebacks() -> None:
    tracebacks.patch()
    from rich.console import NULL_FILE, Console

    local_soup = soup
    with Console(record=True, width=None, file=NULL_FILE) as console:
        try:
            raise ValueError
        except ValueError:
            traceback = Traceback(show_locals=True)

        console.print(traceback)

    captured_locals = traceback.trace.stacks[0].frames[0].locals
    assert captured_locals
    expected = pretty.traverse(local_soup).value_repr
    captured_soup = captured_locals["local_soup"].value_repr

    assert captured_soup == expected

    content = console.export_text()
    assert "chars omitted)" in content
