import asyncio
import os

from aiohttp.resolver import AsyncResolver, ThreadedResolver

from cyberdrop_dl.managers import client_manager


def test_dns_resolver_should_be_async_on_macos_and_linux() -> None:
    loop = asyncio.new_event_loop()
    resolver = loop.run_until_complete(client_manager._get_dns_resolver(loop))
    expected = ThreadedResolver if os.name == "nt" else AsyncResolver
    assert resolver is expected
    loop.close()
