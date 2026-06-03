from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import itertools
import logging
import time
from enum import StrEnum
from http.cookies import SimpleCookie
from typing import TYPE_CHECKING, Any

import aiohttp
from multidict import CIMultiDict, CIMultiDictProxy

from cyberdrop_dl import ddos_guard
from cyberdrop_dl.exceptions import DDOSGuardError, FlaresolverrError
from cyberdrop_dl.progress.scraping import show_msg
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import truncated_preview

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable, Mapping


logger = logging.getLogger(__name__)


class Command(StrEnum):
    CREATE_SESSION = "sessions.create"
    DESTROY_SESSION = "sessions.destroy"
    LIST_SESSIONS = "sessions.list"

    GET_REQUEST = "request.get"
    POST_REQUEST = "request.post"


@dataclasses.dataclass(slots=True)
class Solution:
    content: Any
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
    id: str = dataclasses.field(init=False, default="")

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


class _LazyResponseLog:
    def __init__(self, response: dict[str, Any]) -> None:
        self.resp = response

    def __json__(self) -> dict[str, Any]:
        try:
            html = self.resp["solution"]["response"]
        except LookupError:
            pass
        else:
            if type(html) is str:
                self.resp["solution"]["response"] = truncated_preview(html)

        return self.resp

    def __str__(self) -> str:
        return str(self.__json__())


@dataclasses.dataclass(slots=True)
class Client:
    """Class that handles communication with Flaresolverr."""

    url: AbsoluteHttpURL
    _aiohttp_session: aiohttp.ClientSession

    _session_id: str = dataclasses.field(init=False, default="")
    _session_lock: asyncio.Lock = dataclasses.field(init=False, default_factory=asyncio.Lock)
    _request_lock: asyncio.Lock = dataclasses.field(init=False, default_factory=asyncio.Lock)
    _request_id: Callable[[], int] = dataclasses.field(init=False, default_factory=lambda: itertools.count(1).__next__)
    _down: bool = dataclasses.field(init=False, default=False)

    @property
    def is_down(self) -> bool:
        return self._down

    def __post_init__(self) -> None:
        self.url = self.url.origin() / "v1"

    async def aclose(self) -> None:
        try:
            await self._destroy_session()
        except Exception as e:  # noqa: BLE001
            logger.error(f"Unable to destroy flaresolver session ({e}!r)")

    @contextlib.contextmanager
    def _disable_on_error(self) -> Generator[None]:
        try:
            yield
        except Exception:
            if not self._down:
                self._down = True
                logger.warning("Flaresolverr has been disabled")
            raise

    async def _ensure_session(self) -> None:
        msg = "Unable to create Flaresolverr session"
        if self._down:
            raise FlaresolverrError(msg)

        if self._session_id:
            return

        async with self._session_lock:
            if self._session_id:
                return

            try:
                with self._disable_on_error():
                    await self._create_session()
            except aiohttp.ClientConnectionError as e:
                raise FlaresolverrError(f"Could not connect to Flaresolverr at {self.url} ({e!r})") from None
            except Exception as e:
                raise FlaresolverrError(msg) from e

    async def request(self, url: AbsoluteHttpURL, data: dict[str, Any] | None = None) -> Solution:
        await self._ensure_session()
        try:
            resp = await self._request(
                Command.POST_REQUEST if data else Command.GET_REQUEST,
                url=str(url),
                data=data,
                session=self._session_id,
            )

        except (TypeError, KeyError) as e:
            raise FlaresolverrError("Invalid response from Flaresolverr") from e

        if not resp.ok:
            raise FlaresolverrError(f"Failed to resolve URL with Flaresolverr. {resp.message}")

        if not resp.solution:
            raise FlaresolverrError("Flaresolverr response did not include a solution")

        return resp.solution

    async def _request(self, command: Command, /, data: dict[str, Any] | None = None, **params: Any) -> Response:
        timeout = {}
        if command is Command.CREATE_SESSION:
            timeout.update(timeout=aiohttp.ClientTimeout(total=5 * 60, connect=60))  # 5 minutes to create session

        #  timeout in milliseconds (60s)
        params = {"cmd": str(command), "maxTimeout": 60_000} | params

        if data:
            assert command is Command.POST_REQUEST
            params["postData"] = aiohttp.FormData(data)().decode()

        async with self._request_lock:
            request_id = self._request_id()
            msg = (
                "Destroying Flaresolverr session"
                if command is Command.DESTROY_SESSION
                else f"Waiting for Flaresolverr [{request_id}]"
            )
            with show_msg(msg):
                logger.debug("Making FlareSolverr request [id=%s]\n%s", request_id, params)
                async with self._aiohttp_session.post(self.url, json=params, **timeout) as response:
                    resp_json = await response.json()
                    try:
                        resp = Response.from_dict(resp_json)
                        resp.id = str(request_id)
                    finally:
                        logger.debug(
                            "Finished FlareSolverr request [id=%s]\n%s", request_id, _LazyResponseLog(resp_json)
                        )
                    return resp

    async def _create_session(self) -> None:
        session_id = "cyberdrop-dl"
        params: dict[str, dict[str, str]] = {}

        if proxy := self._aiohttp_session._default_proxy:
            params.update(proxy={"url": str(proxy)})

        resp = await self._request(Command.CREATE_SESSION, session=session_id, **params)
        if not resp.ok:
            raise FlaresolverrError(f"FlareSolverr said: {resp.message}")
        self._session_id = session_id

    async def _destroy_session(self) -> None:
        if self._session_id:
            _ = await self._request(Command.DESTROY_SESSION, session=self._session_id)
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


def verify_solution(cdl_user_agent: str, solution: Solution) -> None:
    mismatch_ua_msg = (
        "Config user_agent and Flaresolverr user_agent do not match:"
        f"\n  Cyberdrop-DL: '{cdl_user_agent}'"
        f"\n  Flaresolverr: '{solution.user_agent}'"
    )

    if type(solution.content) is str:
        try:
            ddos_guard.check_html(solution.content)
        except DDOSGuardError as e:
            if solution.user_agent != cdl_user_agent:
                e.add_note(mismatch_ua_msg)
            raise

    if solution.user_agent != cdl_user_agent:
        logger.warning(f"{mismatch_ua_msg}\n Response was successful but cookies will not be valid")
