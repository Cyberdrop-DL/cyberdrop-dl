import os
from collections.abc import AsyncGenerator

import aiohttp
import pytest

from cyberdrop_dl.clients.flaresolverr import Client, Command
from cyberdrop_dl.url_objects import AbsoluteHttpURL

ENV_NAME = "CDL_FLARESOLVERR"
FLARESOLVER_URL = os.environ.get(ENV_NAME, "")  # or "http://localhost:8191"

pytestmark = pytest.mark.skipif(not FLARESOLVER_URL, reason=f"{ENV_NAME} environment variable is not set")


@pytest.fixture
async def flaresolverr() -> AsyncGenerator[Client]:
    async with aiohttp.ClientSession() as session:
        flare = Client(AbsoluteHttpURL(FLARESOLVER_URL) / "v1", session)
        yield flare


def test_flaresolver(flaresolverr: Client) -> None:
    assert flaresolverr.url
    assert flaresolverr._request_id() == 1
    assert flaresolverr._request_id() == 2


async def test_create_session(flaresolverr: Client) -> None:
    assert flaresolverr._session_id == ""
    resp = await flaresolverr._request(Command.CREATE_SESSION, session="cyberdrop-dl")
    assert resp.ok
    assert "Session created successfully" in resp.message or "Session already exists" in resp.message
    assert resp.solution is None
    resp = await flaresolverr._request(Command.DESTROY_SESSION, session="cyberdrop-dl")
    assert "The session has been removed" in resp.message


async def test_create_session_methods(flaresolverr: Client) -> None:
    assert flaresolverr._session_id == ""
    await flaresolverr._create_session()
    assert flaresolverr._session_id == "cyberdrop-dl"
    await flaresolverr._destroy_session()
    assert flaresolverr._session_id == ""


async def test_request_w_solution(flaresolverr: Client) -> None:
    url = AbsoluteHttpURL("https://google.com")
    solution = await flaresolverr.request(url)
    assert solution.status == 200
    assert solution.url != url  # should have www. as prefix
    assert solution.user_agent
    assert isinstance(solution.content, str)
    assert isinstance(solution.user_agent, str)
    assert "html" in solution.content
    assert solution.cookies
    for cookie in solution.cookies.values():
        assert url.host in cookie["domain"]
