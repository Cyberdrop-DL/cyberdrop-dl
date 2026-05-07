import ssl
import sys

import aiohttp
import pytest
import truststore

from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.manager import Manager
from cyberdrop_dl.managers.client_manager import ClientManager, _make_ssl_context


@pytest.fixture
def client(manager: Manager) -> ClientManager:
    return ClientManager(manager)


async def test_context_manager(client: ClientManager) -> None:
    with pytest.raises(AttributeError):
        _ = client._session

    with pytest.raises(AttributeError):
        _ = client._download_session

    assert client._curl_session is None

    async with client:
        assert type(client._session) is aiohttp.ClientSession
        assert type(client._download_session) is aiohttp.ClientSession
        assert client._curl_session is None

        if sys.implementation.name == "cpython":
            from curl_cffi.requests import AsyncSession

            assert type(client.curl_session) is AsyncSession
        else:
            with pytest.raises(ScrapeError):
                _ = client.curl_session
                # test_ssl_context.py


class TestMakeSSLContext:
    def test_none_or_empty_string_returns_false(self) -> None:
        assert _make_ssl_context(None) is False
        assert _make_ssl_context("") is False

    def test_certifi_returns_default_context_with_certifi_bundle(self) -> None:
        ctx = _make_ssl_context("certifi")
        assert type(ctx) is ssl.SSLContext
        assert ctx.check_hostname is True
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_truststore_returns_truststore_context(self) -> None:
        ctx = _make_ssl_context("truststore")
        assert isinstance(ctx, truststore.SSLContext)

    def test_truststore_plus_certifi_returns_combined_context(self) -> None:
        ctx = _make_ssl_context("truststore+certifi")
        assert type(ctx) is truststore.SSLContext

    def test_unknown_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="foobar"):
            _make_ssl_context("foobar")
