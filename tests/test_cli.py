import pytest

from cyberdrop_dl.__main__ import run_cdl


@pytest.mark.parametrize(
    "command, text",
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
