from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import itertools
import time
from contextvars import ContextVar
from enum import StrEnum
from http.cookies import SimpleCookie
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, TypedDict, Unpack

import aiohttp
from multidict import CIMultiDict, CIMultiDictProxy

from cyberdrop_dl import ddos_guard
from cyberdrop_dl.clients import HttpMethod, get_logger
from cyberdrop_dl.exceptions import CloudflareBlockedError, DDOSGuardError, FlaresolverrError
from cyberdrop_dl.progress.scraping import show_msg
from cyberdrop_dl.signature import dataclass_repr
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import truncated_preview

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Generator, Iterable, Mapping


logger = get_logger(__name__)
USER_AGENT: ContextVar[str] = ContextVar("USER_AGENT")

MAX_TIMEOUT = 60
MAX_TIMEOUT_MILIS = MAX_TIMEOUT * 1000
_CF_BLOCKED_MSG = "Cloudflare has blocked this request"


class _InvalidResponseError(FlaresolverrError): ...


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
    turnstile_token: str | None = None
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
            turnstile_token=solution.get("turnstile_token"),
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


DEFAULT_TIMEOUT = aiohttp.ClientTimeout(sock_read=MAX_TIMEOUT, sock_connect=MAX_TIMEOUT)


@dataclasses.dataclass(slots=True)
class Request:
    command: RequestCommand
    payload: dict[str, Any]
    timeout: aiohttp.ClientTimeout = dataclasses.field(default_factory=lambda: DEFAULT_TIMEOUT)

    def __post_init__(self) -> None:
        wait: int = self.payload.get("waitInSeconds") or 0
        self.timeout = _merge_timeouts(
            self.timeout, aiohttp.ClientTimeout(sock_read=wait + MAX_TIMEOUT, sock_connect=MAX_TIMEOUT)
        )

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
        payload: dict[str, Any] = {"cmd": str(command), "maxTimeout": MAX_TIMEOUT_MILIS, "url": str(url)}
        if wait := max(wait or 0, config.wait):
            payload["waitInSeconds"] = wait

        if config.use_session and session:
            payload["session"] = session
        elif config.proxy:
            payload["proxy"] = {"url": str(config.proxy)}

        return cls(command, payload)


@dataclass_repr("resp")
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


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Config:
    url: AbsoluteHttpURL
    wait: int = 0
    proxy: AbsoluteHttpURL | None = None
    concurrency: int = 1
    use_session: bool = True


@dataclass_repr("session_lock", "session_timeout", "sem")
class Limiter:
    def __init__(self, concurrency: int) -> None:
        self.session_lock: asyncio.Lock = asyncio.Lock()
        self.session_timeout: aiohttp.ClientTimeout = aiohttp.ClientTimeout(sock_read=5 * 60, sock_connect=60)
        self.sem: asyncio.BoundedSemaphore = asyncio.BoundedSemaphore(concurrency)


@dataclass_repr("config", "session", "limiter", "is_down")
class Client:
    """Class that handles communication with Flaresolverr."""

    MAX_INVALID_RESPONSES: ClassVar[int] = 5

    def __init__(self, http: aiohttp.ClientSession, config: Config) -> None:
        self.http: aiohttp.ClientSession = http
        self.config: Config = config
        self.limiter: Limiter = Limiter(config.concurrency)
        self.session: str | None = None
        self.request_id: Callable[[], int] = itertools.count(1).__next__
        self.is_down: bool = False
        self._invalid_responses: int = 0

    async def aclose(self) -> None:
        if not self.session:
            return
        try:
            await self.destroy_session(self.session)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Unable to destroy flaresolver session ({e}!r)")
        finally:
            self.session = None

    def disable(self, reason: str | None = None) -> None:
        if not self.is_down:
            self.is_down = True
            msg = "Flaresolverr has been disabled"
            if reason:
                msg += f" ({reason})"
            logger.warning(msg)

    @contextlib.contextmanager
    def _disable_on_error(self) -> Generator[None]:
        try:
            yield
        except aiohttp.ClientError as e:
            self.disable()
            self.raise_conn_error(e)
        except CloudflareBlockedError:
            raise
        except _InvalidResponseError:
            self._invalid_responses += 1
            if self._invalid_responses > self.MAX_INVALID_RESPONSES:
                self.disable(f"Too many invalid/missing solutions [{self.MAX_INVALID_RESPONSES}+]")
            raise
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
            resp = await self._request(req.command, req.payload, timeout=req.timeout)
            if not resp.ok:
                if _CF_BLOCKED_MSG in resp.message:
                    raise CloudflareBlockedError(resp.message)
                raise _InvalidResponseError(f"Failed to resolve URL with Flaresolverr. {resp.message}")

            if not resp.solution:
                raise _InvalidResponseError("Flaresolverr response did not include a solution")

            return resp.solution

    async def _request(
        self,
        command: Command,
        /,
        json: dict[str, Any],
        *,
        timeout: aiohttp.ClientTimeout = DEFAULT_TIMEOUT,  # noqa: ASYNC109
    ) -> Response:
        payload = {"cmd": str(command), "maxTimeout": MAX_TIMEOUT_MILIS} | json
        async with self._new_request(command) as request_id:
            logger.traffic("Making FlareSolverr request [id=%s]\n%s", request_id, payload)
            async with self.http.post(
                self.config.url, json=payload, timeout=_merge_timeouts(self.http.timeout, timeout)
            ) as response:
                data = await response.json()
                try:
                    return Response.parse(request_id, data)
                except (TypeError, KeyError) as e:
                    raise _InvalidResponseError("Invalid response from Flaresolverr") from e
                finally:
                    logger.traffic("Finished FlareSolverr request [id=%s]\n%s", request_id, _LazyResponseLog(data))

    async def create_session(self, name: str, *, proxy: AbsoluteHttpURL | None = None) -> None:
        self.check_can_connect()
        payload: dict[str, Any] = {"session": name}

        if proxy:
            payload["proxy"] = {"url": str(proxy)}

        resp = await self._request(Command.CREATE_SESSION, payload, timeout=self.limiter.session_timeout)

        if not resp.ok:
            self.disable("Unable to create session")
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


async def verify_solution(cdl_user_agent: str, solution: Solution) -> None:
    mismatch_ua_msg = (
        "Config user_agent and Flaresolverr user_agent do not match:"
        f"\n  Cyberdrop-DL: '{cdl_user_agent}'"
        f"\n  Flaresolverr: '{solution.user_agent}'"
    )

    USER_AGENT.set(solution.user_agent)

    if type(solution.content) is str:
        try:
            await ddos_guard.check_html(solution.content)
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


def _merge_timeouts(a: aiohttp.ClientTimeout, b: aiohttp.ClientTimeout) -> aiohttp.ClientTimeout:
    def max_or_none(val: float | None, val2: float | None) -> float | None:
        if val is None and val2 is None:
            return None

        return max(val or 0, val2 or 0)

    return aiohttp.ClientTimeout(
        total=max_or_none(a.total, b.total),
        connect=max_or_none(a.connect, b.connect),
        sock_read=max_or_none(a.sock_read, b.sock_read),
        sock_connect=max_or_none(a.sock_connect, b.sock_connect),
        ceil_threshold=max(a.ceil_threshold, b.ceil_threshold),
    )
