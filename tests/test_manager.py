from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

import pytest

if TYPE_CHECKING:
    from pydantic import BaseModel

    from cyberdrop_dl.managers.manager import Manager

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
