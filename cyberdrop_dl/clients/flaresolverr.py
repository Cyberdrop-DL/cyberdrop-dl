from __future__ import annotations

import asyncio
import dataclasses
import itertools
import logging
import time
from enum import StrEnum
from http.cookies import SimpleCookie
from typing import TYPE_CHECKING, Any

import aiohttp
from multidict import CIMultiDict, CIMultiDictProxy

from cyberdrop_dl.exceptions import DDOSGuardError
from cyberdrop_dl.progress.scraping import show_msg
from cyberdrop_dl.url_objects import AbsoluteHttpURL

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping


logger = logging.getLogger(__name__)


class Command(StrEnum):
    CREATE_SESSION = "sessions.create"
    DESTROY_SESSION = "sessions.destroy"
    LIST_SESSIONS = "sessions.list"

    GET_REQUEST = "request.get"
    POST_REQUEST = "request.post"


@dataclasses.dataclass(slots=True)
class Solution:
    content: str
    cookies: SimpleCookie
    headers: CIMultiDictProxy[str]
    url: AbsoluteHttpURL
    user_agent: str
    status: int

    @staticmethod
    def from_dict(solution: Mapping[str, Any]) -> Solution:
        return Solution(
            status=int(solution["status"]),
            cookies=_parse_cookies(solution.get("cookies") or ()),
            user_agent=solution["userAgent"],
            content=solution["response"],
            url=AbsoluteHttpURL(solution["url"]),
            headers=CIMultiDictProxy(CIMultiDict(solution["headers"])),
        )


@dataclasses.dataclass(slots=True)
class Response:
    status: str
    message: str
    solution: Solution | None

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @staticmethod
    def from_dict(resp: Mapping[str, Any]) -> Response:
        return Response(
            status=resp["status"],
            message=resp["message"],
            solution=Solution.from_dict(sol) if (sol := resp.get("solution")) else None,
        )


@dataclasses.dataclass(slots=True)
class FlareSolverrClient:
    """Class that handles communication with flaresolverr."""

    url: AbsoluteHttpURL
    _aiohttp_session: aiohttp.ClientSession

    _session_id: str = dataclasses.field(init=False, default="")
    _session_lock: asyncio.Lock = dataclasses.field(init=False, default_factory=asyncio.Lock)
    _request_lock: asyncio.Lock = dataclasses.field(init=False, default_factory=asyncio.Lock)
    _request_id: Callable[[], int] = dataclasses.field(init=False, default_factory=lambda: itertools.count(1).__next__)
    _down: bool = dataclasses.field(init=False, default=False)

    def __post_init__(self) -> None:
        self.url = self.url.origin() / "v1"

    async def aclose(self) -> None:
        try:
            await self._destroy_session()
        except Exception as e:
            logger.error(f"Unable to destroy flaresolver session ({e})")

    async def _ensure_session(self) -> None:
        msg = "Unable to create Flaresolverr session"
        if self._down:
            raise RuntimeError(msg)

        if self._session_id:
            return

        async with self._session_lock:
            if self._session_id:
                return

            try:
                await self._create_session()
            except Exception as e:
                self._down = True
                logger.exception(msg)
                raise RuntimeError(msg) from e

    async def request(self, url: AbsoluteHttpURL, data: dict[str, Any] | None = None) -> Solution:

        await self._ensure_session()
        invalid_response_error = DDOSGuardError("Invalid response from flaresolverr")
        try:
            resp = await self._request(
                Command.POST_REQUEST if data else Command.GET_REQUEST,
                url=str(url),
                data=data,
                session=self._session_id,
            )

        except (TypeError, KeyError) as e:
            raise invalid_response_error from e

        if not resp.ok:
            raise DDOSGuardError(f"Failed to resolve URL with flaresolverr. {resp.message}")

        if not resp.solution:
            raise invalid_response_error

        return resp.solution

    async def _request(self, command: Command, /, data: dict[str, Any] | None = None, **params: Any) -> Response:
        timeout = {}
        if command is Command.CREATE_SESSION:
            timeout.update(timeout=aiohttp.ClientTimeout(total=5 * 60, connect=60))  # 5 minutes to create session

        #  timeout in milliseconds (60s)
        params = {"cmd": command, "maxTimeout": 60_000} | params

        if data:
            assert command is Command.POST_REQUEST
            params["postData"] = aiohttp.FormData(data)().decode()

        async with self._request_lock:
            request_id = self._request_id()
            msg = (
                "Destroying flaresolverr session"
                if command is Command.DESTROY_SESSION
                else f"Waiting for flaresolverr [{request_id}]"
            )
            with show_msg(msg):
                logger.debug(f"Making FlareSolverr request #{request_id} with {params = }")
                async with self._aiohttp_session.post(self.url, json=params, **timeout) as response:
                    return Response.from_dict(await response.json())

    async def _create_session(self) -> None:
        session_id = "cyberdrop-dl"
        params: dict[str, dict[str, str]] = {}

        if proxy := self._aiohttp_session._default_proxy:
            params.update(proxy={"url": str(proxy)})

        resp = await self._request(Command.CREATE_SESSION, session=session_id, **params)
        if not resp.ok:
            raise RuntimeError(f"FlareSolverr said: {resp.message}")
        self._session_id = session_id

    async def _destroy_session(self) -> None:
        if self._session_id:
            _ = await self._request(Command.DESTROY_SESSION)
            self._session_id = ""


def _parse_cookies(cookies: Iterable[Mapping[str, Any]]) -> SimpleCookie:
    simple_cookie = SimpleCookie()
    now = time.time()
    for cookie in cookies:
        name: str = cookie["name"]
        simple_cookie[name] = cookie["value"]
        morsel = simple_cookie[name]
        morsel["domain"] = cookie["domain"]
        morsel["path"] = cookie["path"]
        morsel["secure"] = "TRUE" if cookie.get("secure") else ""
        if expires := cookie.get("expiry") or cookie.get("expires"):
            morsel["max-age"] = str(max(0, int(expires) - int(now)))
    return simple_cookie
