from __future__ import annotations

import logging
import platform
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    import asyncio
    import ssl


logger = logging.getLogger(__name__)

_DNS_RESOLVER: type[aiohttp.AsyncResolver] | type[aiohttp.ThreadedResolver] | None = None


async def _get_dns_resolver(
    loop: asyncio.AbstractEventLoop | None = None,
) -> type[aiohttp.AsyncResolver] | type[aiohttp.ThreadedResolver]:
    """Test aiodns with a DNS lookup."""

    # pycares (the underlying C extension that aiodns uses) installs successfully in most cases,
    # but it fails to actually connect to DNS servers on some platforms (e.g., Android).

    if (system := platform.system()) in ("Windows", "Android"):
        logger.warning(
            f"Unable to setup asynchronous DNS resolver. Falling back to thread based resolver. Reason: not supported on {system}"
        )
        return aiohttp.ThreadedResolver

    try:
        import aiodns

        async with aiodns.DNSResolver(loop=loop, timeout=5.0) as resolver:
            _ = await resolver.query_dns("github.com", "A")

    except Exception as e:
        logger.warning(f"Unable to setup asynchronous DNS resolver. Falling back to thread based resolver: {e!r}")
        return aiohttp.ThreadedResolver

    else:
        return aiohttp.AsyncResolver


async def choose_dns_resolver() -> type[aiohttp.AsyncResolver] | type[aiohttp.ThreadedResolver]:
    global _DNS_RESOLVER
    if _DNS_RESOLVER is None:
        _DNS_RESOLVER = await _get_dns_resolver()  # pyright: ignore[reportConstantRedefinition]
    return _DNS_RESOLVER


def new_connector(ssl_context: ssl.SSLContext | bool) -> aiohttp.TCPConnector:
    assert _DNS_RESOLVER is not None
    tcp_conn = aiohttp.TCPConnector(ssl=ssl_context, resolver=_DNS_RESOLVER())
    tcp_conn._resolver_owner = True
    return tcp_conn
