from __future__ import annotations

import asyncio
import logging
from asyncio import subprocess
from typing import TYPE_CHECKING

from cyberdrop_dl import aio
from cyberdrop_dl.crawlers.crawler import Registry
from cyberdrop_dl.logs import setup_console_logging

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import AbsoluteHttpURL

logger = logging.getLogger("cyberdrop_dl.ping")


async def ping(host: str) -> subprocess.Process:
    process = await asyncio.create_subprocess_exec(
        "ping",
        "-c",
        "1",
        host,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    await process.wait()
    return process


async def parse_stderr(process: subprocess.Process) -> str:
    _, stderr = await process.communicate()
    return b"".join(filter(None, stderr.splitlines())).decode()


async def try_ping(url: AbsoluteHttpURL) -> bool:
    process = await ping(url.host)
    if process.returncode == 0:
        return True

    stderr = await parse_stderr(process)
    if not stderr:
        logger.warning("No response from %s but DNS lookup was successful", url)
        return True

    logger.error("Unable to ping %s (%s)", url, stderr)
    return False


async def main() -> None:
    Registry.import_all()

    urls = tuple(crawler.PRIMARY_URL for crawler in Registry.concrete)
    logger.info(f"Pinning {len(urls):,} hosts")
    results = await aio.map(try_ping, urls, task_limit=30)
    success = sum(1 for _ in filter(None, results))
    errors = len(results) - success
    logger.info(f"Success: {success:,}")
    logger.info(f"Errors: {errors:,}")


if __name__ == "__main__":
    with setup_console_logging():
        asyncio.run(main())
