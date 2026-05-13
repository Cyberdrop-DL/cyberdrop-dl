import pytest

from cyberdrop_dl import program_ui
from cyberdrop_dl.__main__ import run_cdl


def test_startup(capsys: pytest.CaptureFixture[str]) -> None:
    # This is just to test that cyberdrop is able to run in the current python version
    msg = "main UI started successfully"

    def main_ui(*_) -> None:
        print(msg)

    with pytest.MonkeyPatch.context() as m:
        m.setattr(program_ui, "run", main_ui)
        run_cdl(())
        captured = capsys.readouterr()
        output = captured.out
        assert msg in output


def test_async_startup(caplog: pytest.LogCaptureFixture) -> None:
    run_cdl(("--download",))
    assert "Finished downloading. Enjoy :)" in caplog.text
