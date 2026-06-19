import pytest

from cyberdrop_dl import __version__
from cyberdrop_dl.__main__ import run_cdl
from cyberdrop_dl.cli.report import generate_report


@pytest.mark.parametrize(
    ("command", "text"),
    [
        ("--help", "Bulk asynchronous downloader for multiple file hosts"),
        ("show", "cyberdrop-dl supported sites"),
    ],
)
def test_command_by_console_output(capsys: pytest.CaptureFixture[str], command: str, text: str) -> None:
    try:
        run_cdl(command.split())
    except SystemExit:
        pass
    output = capsys.readouterr().out
    assert text in output


def test_report() -> None:
    report = generate_report()

    for value in "cyberdrop-dl", __version__, "aiohttp", "GIL enabled":
        assert value in report
