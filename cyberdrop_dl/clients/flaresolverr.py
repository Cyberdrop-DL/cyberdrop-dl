from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import itertools
import time
from enum import StrEnum
from http.cookies import SimpleCookie
from typing import TYPE_CHECKING, Any, Literal, Self, TypedDict, Unpack

import aiohttp
from multidict import CIMultiDict, CIMultiDictProxy

from cyberdrop_dl import ddos_guard
from cyberdrop_dl.clients import HttpMethod, get_logger
from cyberdrop_dl.exceptions import DDOSGuardError, FlaresolverrError
from cyberdrop_dl.progress.scraping import show_msg
from cyberdrop_dl.signature import simple_repr
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import truncated_preview

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Generator, Iterable, Mapping


logger = get_logger(__name__)

MAX_TIMEOUT = 60_000


class Command(StrEnum):
    CREATE_SESSION = "sessions.create"
    DESTROY_SESSION = "sessions.destroy"
    LIST_SESSIONS = "sessions.list"

    GET_REQUEST = "request.get"
    POST_REQUEST = "request.post"


type RequestCommand = Literal[Command.GET_REQUEST, Command.POST_REQUEST]


class RequestParams(TypedDict, total=False):
    method: HttpMethod
    data: dict[str, Any] | None
    wait: int


@dataclasses.dataclass(slots=True, kw_only=True)
class Solution:
    content: Any
    cookies: SimpleCookie
    headers: CIMultiDictProxy[str]
    url: AbsoluteHttpURL
    user_agent: str
    status: int
    id: str = dataclasses.field(init=False, default="")

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


@dataclasses.dataclass(frozen=True, slots=True, order=True, kw_only=True)
class Response:
    id: str
    status: str
    message: str
    solution: Solution | None

    def __post_init__(self) -> None:
        if self.solution:
            self.solution.id = self.id

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    @staticmethod
    def parse(request_id: int, resp: Mapping[str, Any]) -> Response:
        return Response(
            id=str(request_id),
            status=resp["status"],
            message=resp["message"],
            solution=Solution.from_dict(sol) if (sol := resp.get("solution")) else None,
        )


@dataclasses.dataclass(slots=True, frozen=True)
class Request:
    command: RequestCommand
    payload: dict[str, Any]
    aiohttp_params: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        wait: int | None = self.payload.get("waitInSeconds")
        if wait and "timeout" not in self.aiohttp_params:
            self.aiohttp_params["timeout"] = aiohttp.ClientTimeout(sock_read=wait + 60, sock_connect=60)

    @classmethod
    def build(
        cls,
        command: RequestCommand,
        url: AbsoluteHttpURL,
        /,
        config: Config,
        *,
        wait: int | None,
        session: str | None,
    ) -> Self:
        payload: dict[str, Any] = {"cmd": str(command), "maxTimeout": MAX_TIMEOUT, "url": str(url)}
        if wait := max(wait or 0, config.wait):
            payload["waitInSeconds"] = wait

        if config.use_session and session:
            payload["session"] = session
        elif config.proxy:
            payload["proxy"] = {"url": str(config.proxy)}

        return cls(command, payload, {})


class _LazyResponseLog:
    def __init__(self, resp: dict[str, Any]) -> None:
        self.resp: dict[str, Any] = resp

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

    __repr__ = simple_repr("resp")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Config:
    url: AbsoluteHttpURL
    wait: int = 0
    proxy: AbsoluteHttpURL | None = None
    concurrency: int = 1
    use_session: bool = True


class Limiter:
    def __init__(self, concurrency: int) -> None:
        self.session_lock: asyncio.Lock = asyncio.Lock()
        self.session_timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(sock_read=5 * 60, sock_connect=60)
        self.sem: asyncio.BoundedSemaphore = asyncio.BoundedSemaphore(concurrency)

    __repr__ = simple_repr("session_lock", "session_timeout", "sem")


class Client:
    """Class that handles communication with Flaresolverr."""

    def __init__(self, http: aiohttp.ClientSession, config: Config) -> None:
        self.http: aiohttp.ClientSession = http
        self.config: Config = config
        self.limiter: Limiter = Limiter(config.concurrency)
        self.session: str | None = None
        self.request_id: Callable[[], int] = itertools.count(1).__next__
        self.is_down: bool = False

    __repr__ = simple_repr("config", "session", "limiter", "is_down")

    async def aclose(self) -> None:
        if not self.session:
            return
        try:
            await self.destroy_session(self.session)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Unable to destroy flaresolver session ({e}!r)")
        finally:
            self.session = None

    def disable(self) -> None:
        if not self.is_down:
            self.is_down = True
            logger.warning("Flaresolverr has been disabled")

    @contextlib.contextmanager
    def _disable_on_error(self) -> Generator[None]:
        try:
            yield
        except aiohttp.ClientError as e:
            self.disable()
            self.raise_conn_error(e)
        except Exception:
            self.disable()
            raise

    def raise_conn_error(self, e: Exception | None = None):
        msg = f"Could not connect to Flaresolverr at {self.config.url}"
        if e is None:
            raise FlaresolverrError(msg)
        raise FlaresolverrError(f"{msg} ({e!r})") from None

    def check_can_connect(self) -> None:
        if self.is_down:
            self.raise_conn_error()

    async def _ensure_session(self) -> None:
        if self.session:
            return

        async with self.limiter.session_lock:
            if self.session:
                return

            session_name = _default_session_name()
            try:
                with self._disable_on_error():
                    await self.create_session(session_name, proxy=self.config.proxy)
            except FlaresolverrError:
                raise
            except Exception as e:
                raise FlaresolverrError("Unable to create Flaresolverr session") from e
            else:
                self.session = session_name

    @contextlib.asynccontextmanager
    async def _new_request(self, command: Command) -> AsyncGenerator[int]:
        async with self.limiter.sem:
            request_id = self.request_id()
            msg = (
                "Destroying Flaresolverr session"
                if command is Command.DESTROY_SESSION
                else f"Waiting for Flaresolverr [{request_id}]"
            )
            with show_msg(msg):
                yield request_id

    async def request(self, url: AbsoluteHttpURL, **params: Unpack[RequestParams]) -> Solution:
        self.check_can_connect()
        if self.config.use_session:
            await self._ensure_session()
        with self._disable_on_error():
            req = build_request(url, self.config, params, self.session)
            resp = await self._request(req.command, req.payload, **req.aiohttp_params)
            if not resp.ok:
                raise FlaresolverrError(f"Failed to resolve URL with Flaresolverr. {resp.message}")

            if not resp.solution:
                raise FlaresolverrError("Flaresolverr response did not include a solution")

            return resp.solution

    async def _request(self, command: Command, /, json: dict[str, Any], **aiohttp_params: Any) -> Response:
        payload = {"cmd": str(command), "maxTimeout": MAX_TIMEOUT} | json

        async with self._new_request(command) as request_id:
            logger.traffic("Making FlareSolverr request [id=%s]\n%s", request_id, payload)
            async with self.http.post(self.config.url, json=payload, **aiohttp_params) as response:
                data = await response.json()
                try:
                    return Response.parse(request_id, data)
                except (TypeError, KeyError) as e:
                    raise FlaresolverrError("Invalid response from Flaresolverr") from e
                finally:
                    logger.traffic("Finished FlareSolverr request [id=%s]\n%s", request_id, _LazyResponseLog(data))

    async def create_session(self, name: str, *, proxy: AbsoluteHttpURL | None = None) -> None:
        self.check_can_connect()
        payload: dict[str, Any] = {"session": name}

        if proxy:
            payload["proxy"] = {"url": str(proxy)}

        resp = await self._request(Command.CREATE_SESSION, payload, timeout=self.limiter.session_timeout)

        if not resp.ok:
            raise FlaresolverrError(f"Flaresolverr said: {resp.message}")

    async def destroy_session(self, name: str) -> None:
        self.check_can_connect()
        resp = await self._request(Command.DESTROY_SESSION, {"session": name}, timeout=self.limiter.session_timeout)
        if not resp.ok:
            raise FlaresolverrError(f"Flaresolverr said: {resp.message}")


def _default_session_name() -> str:
    import os
    import socket

    return f"cyberdrop-dl @{socket.gethostname()} (PID{os.getpid()})"


def _cmd_from_http_method(method: HttpMethod) -> RequestCommand:
    match method:
        case "GET" | "HEAD":
            return Command.GET_REQUEST
        case "POST" | "PUT" | "DELETE":
            return Command.POST_REQUEST
        case _:
            raise ValueError(f"Unsupported HTTP method for Flaresolverr: {method}")


def build_request(url: AbsoluteHttpURL, config: Config, params: RequestParams, session: str | None = None) -> Request:
    command = _cmd_from_http_method(params.get("method", "GET"))
    if params.get("data") is not None:
        command = Command.POST_REQUEST

    req = Request.build(command, url, config, wait=params.get("wait"), session=session)
    if (data := params.get("data")) is not None:
        req.payload["postData"] = aiohttp.FormData(data)().decode()

    return req


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
        msg = (
            f"{mismatch_ua_msg}\n Response was successful but cookies will not be valid"
            if solution.cookies
            else mismatch_ua_msg
        )
        logger.warning(msg)

    if not solution.cookies:
        logger.warning("Got empty cookies from Flaresolverr request %s", solution.id)
