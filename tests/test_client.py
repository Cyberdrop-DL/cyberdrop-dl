import ssl
import sys

import aiohttp
import pytest

from cyberdrop_dl.clients.http import HTTPClient, HTTPConfig
from cyberdrop_dl.config import Config
from cyberdrop_dl.exceptions import ScrapeError


@pytest.fixture
def client() -> HTTPClient:
    return HTTPClient(Config())


def test_initial_state(client: HTTPClient) -> None:
    assert client._cookies is None
    assert client._flaresolverr is None
    assert isinstance(client._ssl_context, ssl.SSLContext)
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
        assert session.requote_redirect_url is False


def test_http_config_combine_returns_a_new_config() -> None:
    config_1 = HTTPConfig(headers={"a": "b"}, rate_limit=(3, 1))
    config_2 = HTTPConfig(headers={"c": "d"}, rate_limit=(3, 1))
    config_3 = config_1 | config_2
    assert config_3 is not config_1
    assert config_3 is not config_2


def test_http_config_combine_returns_a_new_headers_dict() -> None:
    config_1 = HTTPConfig(rate_limit=(3, 1))
    config_2 = HTTPConfig(headers={"c": "d"}, rate_limit=(2, 1))
    config_3 = config_1 | config_2
    assert config_3.headers == config_2.headers
    assert config_3.headers is not config_2.headers


def test_http_config_combine_is_not_permutable() -> None:
    config_1 = HTTPConfig(headers={"a": "b"}, rate_limit=(3, 1))
    config_2 = HTTPConfig(headers={"c": "d"}, rate_limit=(3, 1))
    assert config_1 | config_2 == config_2 | config_1
    config_3 = HTTPConfig(headers={"c": "d"}, rate_limit=(100, 1))
    assert config_1 | config_3 != config_3 | config_1


def test_http_config_combine_result() -> None:
    config_1 = HTTPConfig(headers={"a": "b", "h": "l"}, rate_limit=(3, 1))
    config_2 = HTTPConfig(headers={"a": "another", "c": "d"}, rate_limit=(100, 6))
    config_3 = config_1 | config_2
    assert config_3.headers == {"a": "another", "h": "l", "c": "d"}
    assert config_3.rate_limit == (100, 6)
    config_4 = config_2 | config_1
    assert config_4.headers == {"a": "b", "h": "l", "c": "d"}
    assert config_4.rate_limit == (3, 1)


def test_http_config_as_decorator() -> None:
    config_1 = HTTPConfig(headers={"a": "b", "h": "l"}, rate_limit=(3, 1))
    config_2 = HTTPConfig(headers={"a": "another", "c": "d"}, rate_limit=(100, 6))

    @config_1
    class A:
        pass

    assert HTTPConfig.get(A) is config_1

    B = config_2(A)

    assert HTTPConfig.get(B) == config_1 | config_2
