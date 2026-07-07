from pathlib import Path

import pytest

from cyberdrop_dl.__main__ import run_cdl


def test_async_startup(tmp_cwd: Path, caplog: pytest.LogCaptureFixture) -> None:
    file = "URLs.txt"
    (tmp_cwd / file).touch()
    run_cdl(("download", "--input-file", file))
    assert "Finished downloading. Enjoy :)" in caplog.text
