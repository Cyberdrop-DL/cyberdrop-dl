import os
from collections.abc import AsyncGenerator

import aiohttp
import pytest

from cyberdrop_dl.clients import HttpMethod
from cyberdrop_dl.clients.flaresolverr import (
    Client,
    Command,
    Config,
    Request,
    RequestCommand,
    _cmd_from_http_method,
    _default_session_name,
)
from cyberdrop_dl.url_objects import AbsoluteHttpURL

ENV_NAME = "CDL_FLARESOLVERR"
FLARESOLVER_URL = os.environ.get(ENV_NAME, "")  # or "http://localhost:8191"


def needs_flaresolverr() -> pytest.MarkDecorator:
    return pytest.mark.skipif(not FLARESOLVER_URL, reason=f"{ENV_NAME} environment variable is not set")


@pytest.fixture
async def flaresolverr() -> AsyncGenerator[Client]:
    async with aiohttp.ClientSession() as session:
        yield Client(
            session,
            Config(
                url=AbsoluteHttpURL(FLARESOLVER_URL) / "v1",
                use_session=True,
            ),
        )


@needs_flaresolverr()
def test_flaresolver(flaresolverr: Client) -> None:
    assert flaresolverr.config.url
    assert flaresolverr.request_id() == 1
    assert flaresolverr.request_id() == 2


@needs_flaresolverr()
async def test_create_session(flaresolverr: Client) -> None:
    assert flaresolverr.session is None
    resp = await flaresolverr._request(Command.CREATE_SESSION, {"session": "cyberdrop-dl"})
    assert resp.ok
    assert "Session created successfully" in resp.message or "Session already exists" in resp.message
    assert resp.solution is None
    resp = await flaresolverr._request(Command.DESTROY_SESSION, {"session": "cyberdrop-dl"})
    assert "The session has been removed" in resp.message


@needs_flaresolverr()
async def test_create_session_methods(flaresolverr: Client) -> None:
    assert flaresolverr.session is None
    name = "cyberdrop-dl test"
    await flaresolverr.create_session(name)
    assert flaresolverr.session is None
    await flaresolverr.destroy_session(name)
    assert flaresolverr.session is None
    await flaresolverr._ensure_session()
    assert flaresolverr.session
    assert flaresolverr.session == _default_session_name()


@needs_flaresolverr()
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


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("GET", Command.GET_REQUEST),
        ("HEAD", Command.GET_REQUEST),
        ("POST", Command.POST_REQUEST),
        ("PUT", Command.POST_REQUEST),
        ("DELETE", Command.POST_REQUEST),
    ],
)
def test_cmd_from_http_method(method: HttpMethod, expected: Command) -> None:
    assert _cmd_from_http_method(method) is expected


@pytest.mark.parametrize("method", [("PATCH", "QUERY", "OPTIONS")])
def test_cmd_from_unsupported_http_method(method: HttpMethod) -> None:
    with pytest.raises(ValueError):
        _cmd_from_http_method(method)


def _config(*, proxy: bool, use_session: bool) -> Config:
    return Config(
        url=AbsoluteHttpURL("https://example.com"),
        use_session=use_session,
        proxy=AbsoluteHttpURL("https://example.com/proxy") if proxy else None,
    )


@pytest.mark.parametrize(
    ("command", "config", "wait", "session", "expected"),
    [
        (
            Command.GET_REQUEST,
            _config(proxy=True, use_session=True),
            None,
            "sessionA",
            Request(
                Command.GET_REQUEST,
                {
                    "cmd": "request.get",
                    "maxTimeout": 60_000,
                    "url": "https://example.com",
                    "session": "sessionA",
                },
            ),
        ),
        (
            Command.GET_REQUEST,
            _config(proxy=True, use_session=True),
            20,
            "sessionA",
            Request(
                Command.GET_REQUEST,
                {
                    "cmd": "request.get",
                    "maxTimeout": 60_000,
                    "url": "https://example.com",
                    "waitInSeconds": 20,
                    "session": "sessionA",
                },
                {"timeout": aiohttp.ClientTimeout(sock_read=80, sock_connect=60)},
            ),
        ),
        (
            Command.POST_REQUEST,
            _config(proxy=True, use_session=False),
            20,
            "sessionA",
            Request(
                Command.POST_REQUEST,
                {
                    "cmd": "request.post",
                    "maxTimeout": 60_000,
                    "url": "https://example.com",
                    "waitInSeconds": 20,
                    "proxy": {
                        "url": "https://example.com/proxy",
                    },
                },
                {"timeout": aiohttp.ClientTimeout(sock_read=80, sock_connect=60)},
            ),
        ),
    ],
)
def test_request_build(
    command: RequestCommand, config: Config, *, wait: int | None, session: str | None, expected: Request
) -> None:

    req = Request.build(command, AbsoluteHttpURL("https://example.com"), config, wait=wait, session=session)
    assert req.command is expected.command
    assert req.payload == expected.payload
    assert req.aiohttp_params == expected.aiohttp_params
