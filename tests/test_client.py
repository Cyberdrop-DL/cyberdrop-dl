import aiohttp
import pytest
from curl_cffi.requests import AsyncSession

from cyberdrop_dl.manager import Manager
from cyberdrop_dl.managers.client_manager import ClientManager


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
        assert type(client.curl_session) is AsyncSession
