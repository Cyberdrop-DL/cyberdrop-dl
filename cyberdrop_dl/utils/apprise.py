from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
from typing import TYPE_CHECKING

from cyberdrop_dl import aio
from cyberdrop_dl.constants import MAIN_LOG_FILE
from cyberdrop_dl.logs import borrow_logger, export_logs, log_spacer

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterable, Sequence
    from pathlib import Path

    import apprise

    from cyberdrop_dl.models import AppriseURL

logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class _AppriseMessage:
    tag: str
    body: str = "Finished downloading. Enjoy :)"
    title: str = "Cyberdrop-DL"
    body_format: str = "text"
    attachment: str | None = None


async def notify(urls: Sequence[AppriseURL], body: str) -> None:
    if not urls:
        return

    import apprise

    log_spacer()
    logger.info("Sending Apprise notifications ... ")
    apprise_obj = apprise.Apprise()
    should_attach_logs: bool = False

    for webhook in urls:
        should_attach_logs |= webhook.attach_logs
        _ = apprise_obj.add(str(webhook.url.get_secret_value()), tag=sorted(webhook.tags))

    messages = (
        attach_logs_msg := _AppriseMessage(body=body, tag="attach_logs"),
        _AppriseMessage(body=body, tag="no_logs"),
        _AppriseMessage(tag="simplified"),
    )

    if not should_attach_logs:
        await _notify(apprise_obj, messages)
        return

    async with _temp_copy_of_main_log() as file:
        if file:
            attach_logs_msg.attachment = str(file)
        await _notify(apprise_obj, messages)


async def _notify(apprise_obj: apprise.Apprise, messages: Iterable[_AppriseMessage]) -> None:
    with borrow_logger("apprise", level=logging.INFO):
        _ = await aio.gather(
            *(
                apprise_obj.async_notify(
                    title=msg.title,
                    body=msg.body,
                    body_format=msg.body_format,
                    attach=msg.attachment,
                    tag=msg.tag,
                )
                for msg in messages
            )
        )


@contextlib.asynccontextmanager
async def _temp_copy_of_main_log() -> AsyncGenerator[Path | None]:
    async with aio.temp_dir() as temp_dir:
        temp_file = temp_dir / MAIN_LOG_FILE.get().name
        try:
            logs = await asyncio.to_thread(export_logs, size_limit=25 * 1e6)
        except Exception:
            logger.exception("Unable to attach main log for apprise notifications")
            yield
            return

        _ = await aio.write_bytes(temp_file, logs)

        yield temp_file
