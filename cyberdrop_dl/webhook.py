from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import aiohttp

from cyberdrop_dl import context
from cyberdrop_dl.logs import MAX_ATTACHMENT_SIZE, export_logs, log_spacer

if TYPE_CHECKING:
    import yarl

    from cyberdrop_dl.models import AppriseURL


logger = logging.getLogger(__name__)


async def notify(webhook: AppriseURL, body: str) -> None:
    await _notify(
        url=str(webhook.url.get_secret_value()),
        body=body,
        attach_logs=webhook.attach_logs,
    )


async def _notify(url: str, body: str, *, attach_logs: bool) -> None:
    log_spacer()
    form = aiohttp.FormData()
    if attach_logs:
        await _attach_logs(form, size_limit=MAX_ATTACHMENT_SIZE - len(body.encode()))
    form.add_field("username", "cyberdrop-dl")
    form.add_field("content", body)
    await _send_notification(url, form)


async def _attach_logs(form: aiohttp.FormData, size_limit: float) -> None:
    try:
        logs = await asyncio.to_thread(export_logs, size_limit=size_limit)
    except Exception:
        logger.exception("Unable to attach log for webhook notification")
    else:
        form.add_field("file", logs, filename=context.MAIN_LOG_FILE.get().name)


async def _send_notification(url: yarl.URL | str, form: aiohttp.FormData) -> None:
    logger.info("Sending webhook notifications.. ")
    try:
        async with aiohttp.request("POST", url, data=form) as response:
            if response.ok:
                logger.info("Webhook notifications: Success", extra={"color": "green"})
            else:
                try:
                    error: dict[str, Any] = await response.json()
                except Exception:
                    response.raise_for_status()
                    raise
                else:
                    _ = error.pop("content", None)
                    logger.error(f"Webhook notification failed: {error}", extra={"color": "red"})

    except Exception as e:  # noqa: BLE001
        logger.error(f"Unable to send webhook notification: {e!r}")
