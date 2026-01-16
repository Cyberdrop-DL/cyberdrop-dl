import asyncio

from aiohttp import resolver

from cyberdrop_dl import constants
from cyberdrop_dl.managers import client_manager


def test_dns_resolver_should_be_async_on_windows_macos_and_linux() -> None:
    constants.DNS_RESOLVER = None
    loop = asyncio.new_event_loop()
    loop.run_until_complete(client_manager._set_dns_resolver(loop))
    assert constants.DNS_RESOLVER is resolver.AsyncResolver
    loop.close()
