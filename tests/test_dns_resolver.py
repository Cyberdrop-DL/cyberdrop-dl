import asyncio
import os
import ssl

import pytest
import truststore
from aiohttp.resolver import AsyncResolver, ThreadedResolver

from cyberdrop_dl.clients import tcp


def test_dns_resolver_should_be_async_on_macos_and_linux() -> None:
    loop = asyncio.new_event_loop()
    resolver = loop.run_until_complete(tcp._get_dns_resolver(loop))
    expected = ThreadedResolver if os.name == "nt" else AsyncResolver
    assert resolver is expected
    loop.close()


class TestMakeSSLContext:
    def test_none_or_empty_string_returns_false(self) -> None:
        assert tcp.create_ssl_context(None) is False
        assert tcp.create_ssl_context("") is False

    def test_certifi_returns_default_context_with_certifi_bundle(self) -> None:
        ctx = tcp.create_ssl_context("certifi")
        assert type(ctx) is ssl.SSLContext
        assert ctx.check_hostname is True
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_truststore_returns_truststore_context(self) -> None:
        ctx = tcp.create_ssl_context("truststore")
        assert isinstance(ctx, truststore.SSLContext)

    def test_truststore_plus_certifi_returns_combined_context(self) -> None:
        ctx = tcp.create_ssl_context("truststore+certifi")
        assert type(ctx) is truststore.SSLContext

    def test_unknown_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="foobar"):
            tcp.create_ssl_context("foobar")
