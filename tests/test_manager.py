from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

import pytest

from cyberdrop_dl.clients.http import HTTPClient
from cyberdrop_dl.config import Config
from cyberdrop_dl.database import Database
from cyberdrop_dl.dedupe import Czkawka
from cyberdrop_dl.manager import Manager
from cyberdrop_dl.progress import REFRESH_RATE
from cyberdrop_dl.sorter import Sorter

if TYPE_CHECKING:
    from pydantic import BaseModel

    _M = TypeVar("_M", bound=BaseModel)


def update_model(model: _M, **kwargs: Any) -> _M:
    return model.model_validate(model.model_dump() | kwargs)


@pytest.mark.parametrize(
    "webhook, output",
    [
        ("https://example.com", "no_logs=**********"),
        ("attach_logs=https://example.com", "attach_logs=**********"),
    ],
)
def test_args_logging_should_censor_webhook(
    running_manager: Manager, logs: pytest.LogCaptureFixture, webhook: str, output: str
) -> None:
    logs_model = running_manager.config.settings.logs
    running_manager.config.settings.logs = update_model(logs_model, webhook=webhook)
    running_manager.log_config_settings()
    assert logs.messages
    assert "Running cyberdrop-dl " in logs.text
    assert webhook not in logs.text
    webhook_line = next(msg for msg in logs.text.splitlines() if '"webhook"' in msg)
    _, _, webhook_text = webhook_line.partition(":")
    webhook_url = webhook_text.strip().split(" ")[0].replace('"', "").strip()
    assert output == webhook_url


def test_manager_context() -> None:
    config = Config.parse_args(["--refresh-rate", "40"])
    manager = Manager(config=config)

    for attr in ("database", "deduper", "sorter"):
        with pytest.raises(AttributeError):
            getattr(manager, attr)

    assert REFRESH_RATE.get() == 10

    with manager():
        assert type(manager.database) is Database
        assert type(manager.deduper) is Czkawka
        assert type(manager.sorter) is Sorter
        assert type(manager.http_client) is HTTPClient
        assert REFRESH_RATE.get() == 40
