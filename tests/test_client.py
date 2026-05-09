import ssl
import sys

import aiohttp
import pytest

from cyberdrop_dl.clients.http import HTTPClient
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.manager import Manager


@pytest.fixture
def client(manager: Manager) -> HTTPClient:
    return HTTPClient(manager)


def test_initial_state(client: HTTPClient) -> None:
    assert client._cookies is None
    assert client._flaresolverr is None
    assert isinstance(client.ssl_context, ssl.SSLContext)
    assert client.rate_limits == {}


async def test_context_manager(client: HTTPClient) -> None:
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


def test_create_aiohttp_session_outside_loop(client: HTTPClient) -> None:
    with pytest.raises(RuntimeError, match="no running event loop"):
        _ = client.create_aiohttp_session()


async def test_create_aiohttp_session(client: HTTPClient) -> None:
    async with client, client.create_aiohttp_session() as session:
        assert len(session.headers) == 1
        assert session.headers.get("User-agent")
        assert session.cookie_jar is client.cookies
        assert session._raise_for_status is False
        assert session.timeout == client.manager.config.global_settings.rate_limiting_options._aiohttp_timeout
        assert session.requote_redirect_url is False
