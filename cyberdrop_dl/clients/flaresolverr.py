from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import itertools
import time
from enum import StrEnum
from http.cookies import SimpleCookie
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, TypedDict, Unpack

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

    @classmethod
    def build(
        cls, command: RequestCommand, url: AbsoluteHttpURL, config: Config, /, *, wait: int | None, session: str | None
    ) -> Self:
        payload: dict[str, Any] = {"cmd": str(command), "maxTimeout": MAX_TIMEOUT, "url": str(url)}
        aiohttp_params: dict[str, Any] = {}

        if wait := max(wait or 0, config.wait):
            aiohttp_params["timeout"] = aiohttp.ClientTimeout(sock_read=wait + 60, sock_connect=60)
            payload["waitInSeconds"] = wait

        if config.use_session and session:
            payload["session"] = session
        elif config.proxy:
            payload["proxy"] = {"url": str(config.proxy)}

        return cls(command, payload, aiohttp_params)


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

    def __repr__(self) -> str:
        return f"<{type(self).__name__}(resp={self.resp!r})>"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Config:
    url: AbsoluteHttpURL
    concurrency: int = 1
    wait: int = 0
    use_session: bool = True
    proxy: AbsoluteHttpURL | None = None


class Session:
    DEFAULT_NAME: ClassVar[str] = "cyberdrop-dl"
    TIMEOUT: ClassVar[aiohttp.ClientTimeout] = aiohttp.ClientTimeout(sock_read=5 * 60, sock_connect=60)

    def __init__(self, concurrency: int) -> None:
        self.name: str | None = None
        self.lock: asyncio.Lock = asyncio.Lock()
        self.sem: asyncio.BoundedSemaphore = asyncio.BoundedSemaphore(concurrency)
        self.request_id: Callable[[], int] = itertools.count(1).__next__

    __repr__ = simple_repr("name")

    @contextlib.asynccontextmanager
    async def new_request(self, command: Command) -> AsyncGenerator[int]:
        async with self.sem:
            request_id = self.request_id()
            msg = (
                "Destroying Flaresolverr session"
                if command is Command.DESTROY_SESSION
                else f"Waiting for Flaresolverr [{request_id}]"
            )
            with show_msg(msg):
                yield request_id


@dataclasses.dataclass(slots=True)
class Client:
    """Class that handles communication with Flaresolverr."""

    http: aiohttp.ClientSession = dataclasses.field(repr=False)
    config: Config
    session: Session = dataclasses.field(init=False)
    _down: bool = dataclasses.field(init=False, default=False)

    def __post_init__(self) -> None:
        self.session = Session(self.config.concurrency)

    @property
    def is_down(self) -> bool:
        return self._down

    async def aclose(self) -> None:
        try:
            await self._destroy_session()
        except Exception as e:  # noqa: BLE001
            logger.error(f"Unable to destroy flaresolver session ({e}!r)")

    def disable(self) -> None:
        if not self._down:
            self._down = True
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

    async def _ensure_session(self) -> None:
        if self._down:
            self.raise_conn_error()

        if not self.config.use_session:
            return

        if self.session.name:
            return

        async with self.session.lock:
            if self._down:
                self.raise_conn_error()

            if self.session.name:
                return

            try:
                with self._disable_on_error():
                    await self._create_session()
            except FlaresolverrError:
                raise
            except Exception as e:
                raise FlaresolverrError("Unable to create Flaresolverr session") from e

    async def request(self, url: AbsoluteHttpURL, **params: Unpack[RequestParams]) -> Solution:
        await self._ensure_session()
        with self._disable_on_error():
            request = prepare_request(url, self.config, params, self.session.name)
            resp = await self._request(request.command, request.payload, **request.aiohttp_params)
            if not resp.ok:
                raise FlaresolverrError(f"Failed to resolve URL with Flaresolverr. {resp.message}")

            if not resp.solution:
                raise FlaresolverrError("Flaresolverr response did not include a solution")

            return resp.solution

    async def _request(self, command: Command, /, json: dict[str, Any], **aiohttp_params: Any) -> Response:
        payload = {"cmd": str(command), "maxTimeout": MAX_TIMEOUT} | json

        async with self.session.new_request(command) as request_id:
            logger.traffic("Making FlareSolverr request [id=%s]\n%s", request_id, payload)
            async with self.http.post(self.config.url, json=payload, **aiohttp_params) as response:
                resp_json = await response.json()
                try:
                    return Response.parse(request_id, resp_json)
                except (TypeError, KeyError) as e:
                    raise FlaresolverrError("Invalid response from Flaresolverr") from e
                finally:
                    logger.traffic("Finished FlareSolverr request [id=%s]\n%s", request_id, _LazyResponseLog(resp_json))

    async def _create_session(self) -> None:
        payload: dict[str, Any] = {"session": Session.DEFAULT_NAME}

        if self.config.proxy:
            payload["proxy"] = {"url": str(self.config.proxy)}

        resp = await self._request(Command.CREATE_SESSION, payload, timeout=self.session.TIMEOUT)

        if not resp.ok:
            raise FlaresolverrError(f"FlareSolverr said: {resp.message}")

        self.session.name = Session.DEFAULT_NAME

    async def _destroy_session(self) -> None:
        if not self.session.name:
            return

        await self._request(Command.DESTROY_SESSION, {"session": self.session.name}, timeout=self.session.TIMEOUT)
        self.session.name = None


def _cmd_from_http_method(method: HttpMethod) -> RequestCommand:
    match method:
        case "GET" | "HEAD":
            return Command.GET_REQUEST
        case "POST" | "PUT" | "DELETE":
            return Command.POST_REQUEST
        case _:
            raise ValueError(f"Unsupported HTTP method for Flaresolverr: {method}")


def prepare_request(
    url: AbsoluteHttpURL,
    config: Config,
    params: RequestParams,
    session: str | None = None,
) -> Request:
    command = _cmd_from_http_method(params.get("method", "GET"))
    command = Command.POST_REQUEST if params.get("data") is not None else command

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
        logger.warning(f"{mismatch_ua_msg}\n Response was successful but cookies will not be valid")
