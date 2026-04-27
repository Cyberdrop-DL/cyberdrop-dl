import aiohttp
import pytest

try:
    from curl_cffi.requests import AsyncSession
except ImportError:
    AsyncSession = None

from cyberdrop_dl.managers.client_manager import ClientManager
from cyberdrop_dl.managers.manager import Manager


@pytest.fixture
def client(manager: Manager) -> ClientManager:
    return ClientManager(manager)


async def test_context_manager(client: ClientManager) -> None:
    with pytest.raises(AttributeError):
        _ = client._session

    with pytest.raises(AttributeError):
        _ = client._download_session

    if AsyncSession:
        with pytest.raises(AttributeError):
            _ = client._curl_session

    async with client:
        assert type(client._session) is aiohttp.ClientSession
        assert type(client._download_session) is aiohttp.ClientSession
        if AsyncSession:
            assert type(client._curl_session) is AsyncSession
