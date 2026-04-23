from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import aiohttp

from cyberdrop_dl.logs import MAIN_LOG_FILE, export_logs, log_spacer

if TYPE_CHECKING:
    import yarl

    from cyberdrop_dl.models import AppriseURL


logger = logging.getLogger(__name__)


async def send_notification(webhook: AppriseURL, body: str) -> None:
    log_spacer()
    url, form = await _prepare(webhook)
    form.add_field("content", body)
    await _send_notification(url, form)


async def _prepare(webhook: AppriseURL) -> tuple[str, aiohttp.FormData]:
    url = str(webhook.url.get_secret_value())
    form = aiohttp.FormData()
    if webhook.attach_logs:
        try:
            logs = await asyncio.to_thread(export_logs, size_limit=25 * 1e6)
        except Exception:
            logger.exception("Unable to attach log for webhook notification")
        else:
            form.add_field("file", logs, filename=MAIN_LOG_FILE.get().name)

    form.add_field("username", "cyberdrop-dl")
    return url, form


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

    except Exception as e:
        logger.error(f"Unable to send webhook notification: {e!r}")
