from __future__ import annotations

import logging
from typing import Any

import aiohttp

from cyberdrop_dl import __version__ as current

_PYPI_JSON_URL = "https://pypi.org/pypi/cyberdrop-dl-patched/json"
logger = logging.getLogger(__name__)


async def check_latest_pypi(session: aiohttp.ClientSession) -> None:
    logger.info("Checking for updates...")
    try:
        contents = await _request_pypi_info(session)

    except Exception as e:
        logger.error(f"Unable to get latest version information {e!r}")
    else:
        _parse_pypi_resp(contents)


async def _request_pypi_info(session: aiohttp.ClientSession) -> dict[str, Any]:
    async with session.get(
        _PYPI_JSON_URL,
        raise_for_status=True,
        timeout=aiohttp.ClientTimeout(
            sock_read=30,
            sock_connect=20,
        ),
    ) as response:
        return await response.json()


def _parse_pypi_resp(data: dict[str, Any]) -> None:
    latest: str = data["info"]["version"]
    releases: set[str] = set(data["releases"])

    if current not in releases:
        logger.warning(f"You are using an unreleased version of CDL: {current}. Latest stable release {latest}")
    elif current == latest:
        logger.info(f"You are using the latest version of CDL: {current}")
    else:
        logger.warning(f"A new version is available: {latest}")
