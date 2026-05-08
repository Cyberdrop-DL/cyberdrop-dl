import pytest

from cyberdrop_dl.updates import _compare_and_log_version

RELEASES = [
    "5.3.31",
    "5.3.32",
    "5.3.33",
    "6.9.0",
    "6.9.1",
    "7.0.0",
    "7.0.1",
    "7.1.0",
    "7.2.0",
    "7.2.1",
    "8.7.0",
    "8.8.0",
    "8.9.0",
    "9.3.1",
    "9.3.1.dev0",
    "9.4.0",
    "9.4.1",
    "9.4.2",
    "9.4.3",
    "9.5.0",
    "9.5.1",
    "9.6.0",
    "9.7.0",
    "9.7.1.dev0",
    "9.7.1.dev1",
]


def compare(version: str) -> None:
    _compare_and_log_version(RELEASES, current=version, latest="9.7.0")


def test_old_version(logs: pytest.LogCaptureFixture) -> None:
    compare("8.7.0")
    assert "A new version is available" in logs.messages[0]


def test_dev_version(logs: pytest.LogCaptureFixture) -> None:
    compare("9.7.1.dev0")
    assert "You are using a development version" in logs.messages[0]


def test_unreleased_version(logs: pytest.LogCaptureFixture) -> None:
    compare("8.7.0.fakeversion")
    assert "You are using an unreleased version " in logs.messages[0]


def test_current_version(logs: pytest.LogCaptureFixture) -> None:
    compare("9.7.0")
    assert "You are using the latest version" in logs.messages[0]
