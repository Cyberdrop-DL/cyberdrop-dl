import sys

import aiohttp
import pytest

from cyberdrop_dl.clients.client import HTTPClient
from cyberdrop_dl.exceptions import ScrapeError
from cyberdrop_dl.manager import Manager


@pytest.fixture
def client(manager: Manager) -> HTTPClient:
    return HTTPClient(manager)


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
