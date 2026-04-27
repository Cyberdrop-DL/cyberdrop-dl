from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cyberdrop_dl.managers.manager import Manager

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator
    from pathlib import Path

    class Config(pytest.Config):  # type: ignore
        test_crawlers_domains: set[str]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--test-crawlers",
        action="store",
        help="A comma-separated list of crawlers' domains (e.g., 'dropbox.com,jpg5.su').",
        default="",
    )


def pytest_configure(config: Config):
    config.test_crawlers_domains = {
        domain for item in config.getoption("--test-crawlers").split(",") if (domain := item.strip())
    }


def pytest_collection_modifyitems(config: Config, items: list[pytest.Item]) -> None:
    """When running with --test-crawlers, disable all other tests"""
    if not config.test_crawlers_domains:
        return

    selected_tests = []
    deselected_tests = []
    for item in items:
        markers = {marker.name for marker in item.iter_markers()}

        if "crawler_test_case" in markers:
            selected_tests.append(item)
        else:
            deselected_tests.append(item)

    if deselected_tests:
        config.hook.pytest_deselected(items=deselected_tests)
        items[:] = selected_tests


@pytest.fixture(autouse=True)
def tmp_cwd(tmp_path: Path) -> Generator[Path]:
    with pytest.MonkeyPatch.context() as m:
        m.chdir(tmp_path)
        yield tmp_path


@pytest.fixture
async def logs(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    caplog.set_level(10)
    return caplog


@pytest.fixture(scope="function", name="manager")
def post_startup_manager() -> Manager:
    manager = Manager()
    manager.resolve_paths()
    return manager


@pytest.fixture(scope="function")
async def running_manager(manager: Manager) -> AsyncGenerator[Manager]:
    await manager.async_startup()

    async with manager.database:
        yield manager
