from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from cyberdrop_dl.models import AppriseURL
from cyberdrop_dl.webhook import send_notification

if TYPE_CHECKING:
    from collections.abc import Generator

    import pytest

webhook = AppriseURL.model_validate({"url": "https://example.com/webhook", "tags": {"no_logs"}})


@contextlib.contextmanager
def _mock_aiohttp_request(mock_response: AsyncMock) -> Generator[None]:
    with patch("aiohttp.request") as mock_request:
        mock_request.return_value.__aenter__.return_value = mock_response
        yield


async def test_send_webhook_success(caplog: pytest.LogCaptureFixture) -> None:
    mock_response = AsyncMock()
    mock_response.ok = True
    mock_response.status = 200

    with _mock_aiohttp_request(mock_response):
        with caplog.at_level(10):
            await send_notification(webhook, "test")

        assert "Webhook notifications: Success" in caplog.text


async def test_send_webhook_failure_with_json_error(caplog: pytest.LogCaptureFixture) -> None:
    mock_response = AsyncMock()
    mock_response.ok = False
    mock_response.status = 400
    mock_response.json = AsyncMock(return_value={"error": "Bad Request", "content": "details"})

    with _mock_aiohttp_request(mock_response):
        with caplog.at_level(10):
            await send_notification(webhook, "test")

        assert "Webhook notification failed:" in caplog.text
        assert "Bad Request" in caplog.text


async def test_send_webhook_failure_with_non_json_error(caplog: pytest.LogCaptureFixture) -> None:
    mock_response = AsyncMock()
    mock_response.ok = False
    mock_response.status = 500
    mock_response.json = AsyncMock(side_effect=aiohttp.ClientError("JSON error"))

    mock_response.raise_for_status = MagicMock(
        side_effect=aiohttp.ClientResponseError(
            AsyncMock(spec=aiohttp.RequestInfo),
            (),
            status=500,
        )
    )

    with _mock_aiohttp_request(mock_response):
        with caplog.at_level(10):
            await send_notification(webhook, "test")

        assert "ClientResponseError" in caplog.text
