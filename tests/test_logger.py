import logging
from pathlib import Path

import pytest
from rich import get_console

from cyberdrop_dl import logs
from cyberdrop_dl.progress import LiveUI

TEXT = "\n".join(f"line {idx}" for idx in range(1, 5))


def test_logs_capture() -> None:
    with logs.capture_logs() as file:
        logs.logger.setLevel(logging.DEBUG)

        for line in TEXT.splitlines():
            logs.logger.debug(line)

    assert file.getvalue() == TEXT + "\n"


def test_export_logs(tmp_path: Path) -> None:
    log_file = tmp_path / "test-log.log"
    with logs.setup_file_logging(log_file):
        for line in TEXT.splitlines():
            logs.logger.debug(line)

        content = logs.export_logs().decode("utf8")
        with pytest.raises(RuntimeError):
            _ = logs.export_logs(size_limit=1)

    with pytest.raises(LookupError):
        _ = logs.export_logs()

    assert "Debug log file" in content
    for line in TEXT.splitlines():
        assert line in content


class TestBorrowLogger:
    def test_level_and_propagate_restored(self) -> None:
        other = logging.getLogger("third_party_restore")
        other.setLevel(logging.WARNING)
        other.propagate = True

        with logs.borrow_logger("third_party_restore", level=logging.DEBUG):
            assert other.level == logging.DEBUG

        assert other.level == logging.WARNING

    def test_exception_inside_block_restores_state(self) -> None:
        other = logging.getLogger("third_party_exc")
        orig_handler = logging.NullHandler()
        other.addHandler(orig_handler)
        other.setLevel(logging.CRITICAL)

        with pytest.raises(RuntimeError):
            with logs.borrow_logger("third_party_exc", level=logging.INFO):
                assert other.level == logging.INFO
                raise RuntimeError("boom")

        assert other.handlers == [orig_handler]
        assert other.level == logging.CRITICAL


def test_disable_console_logging() -> None:

    logger = logging.getLogger("cyberdrop_dl")
    console = get_console()
    console.record = True
    with console, logs.setup_console_logging():
        logger.info("This msg SHOULD show up")
        with logs.disable_console_logging():
            logger.info("This msg SHOULD NOT show up")

        logger.info("This msg also SHOULD show up")

    text = console.export_text()
    assert "This msg SHOULD show up" in text
    assert "This msg SHOULD NOT show up" not in text
    assert "This msg also SHOULD show up" in text


def test_entering_a_live_disables_console_logging() -> None:
    logger = logging.getLogger("cyberdrop_dl")
    console = get_console()
    console.record = True

    class DummyLiveUI(LiveUI):
        def __rich__(self):
            return "In Live"

    with console, logs.setup_console_logging():
        logger.info("This msg SHOULD show up")
        with DummyLiveUI()(transient=False, force=True):
            logger.info("This msg SHOULD NOT show up")

        logger.info("This msg also SHOULD show up")

    text = console.export_text()
    assert "In Live" in text
    assert "This msg SHOULD show up" in text
    assert "This msg SHOULD NOT show up" not in text
    assert "This msg also SHOULD show up" in text
