from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Self, cast

from multidict import CIMultiDict

from cyberdrop_dl import constants, ddos_guard, signature
from cyberdrop_dl.clients.response import AbstractResponse
from cyberdrop_dl.cookies import make_simple_cookie
from cyberdrop_dl.exceptions import DDOSGuardError
from cyberdrop_dl.utils import truncated_preview
from cyberdrop_dl.utils.filepath import sanitize_filename

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from bs4 import BeautifulSoup
    from curl_cffi.requests.session import HttpMethod

    from cyberdrop_dl.clients import flaresolverr
    from cyberdrop_dl.managers.client_manager import ClientManager
    from cyberdrop_dl.url_objects import AbsoluteHttpURL


logger = logging.getLogger(__name__)


class _LazyRequestLog:
    def __init__(self, params: Mapping[str, Any]) -> None:
        self.params: Mapping[str, Any] = params

    def __json__(self) -> dict[str, Any]:
        params = {k: v for k, v in self.params.items() if v is not None}
        headers = dict(params.pop("headers")) or None
        if headers:
            params.update(headers=headers)
        return params

    def __str__(self) -> str:
        return str(self.__json__())


class _LazyResponseLog:
    def __init__(self, response: AbstractResponse[Any]) -> None:
        self.response = response

    def __json__(self) -> dict[str, Any]:
        resp = self.response.__json__()
        del resp["created_at"]
        if type(content := resp["content"]) is str:
            resp["content"] = truncated_preview(content)
        return resp

    def __str__(self) -> str:
        return str(self.__json__())


@dataclasses.dataclass(slots=True)
class HTTPClient:
    client_manager: ClientManager
    _save_responses_to_disk: bool
    _responses_folder: Path

    @classmethod
    def from_client(cls, client_manager: ClientManager) -> Self:
        return cls(
            client_manager,
            client_manager.manager.config.settings.files.save_pages_html,
            client_manager.manager.config.settings.logs.main_log.parent / "cdl_responses",
        )

    @property
    def _default_headers(self) -> dict[Any, Any]:
        return {}

    @contextlib.asynccontextmanager
    async def _limiter(self, domain: str) -> AsyncGenerator[None]:
        with self.client_manager.request_context(domain):
            domain_limiter = self.client_manager.get_rate_limiter(domain)
            async with self.client_manager.global_rate_limiter, domain_limiter:
                yield

    def _prepare_headers(self, headers: Mapping[str, str] | None = None) -> CIMultiDict[str]:
        """Add default headers and transform it to CIMultiDict"""
        combined = CIMultiDict(self._default_headers)
        if headers:
            headers = CIMultiDict(headers)
            new: set[str] = set()
            for key, value in headers.items():
                if key in new:
                    combined.add(key, value)
                else:
                    combined[key] = value
                    new.add(key)
        return combined

    @contextlib.asynccontextmanager
    async def request(
        self: object,
        url: AbsoluteHttpURL,
        /,
        method: HttpMethod = "GET",
        headers: Mapping[str, str] | None = None,
        impersonate: str | bool | None = None,
        data: Any = None,
        json: Any = None,
        cache_disabled: bool = False,
        **request_params: Any,
    ) -> AsyncGenerator[AbstractResponse[Any]]:
        self = cast("HTTPClient", self)
        request_params["headers"] = headers = self._prepare_headers(headers)
        request_params["data"] = data
        request_params["json"] = json

        if method == "GET" and (data or json):
            method = "POST"

        impersonate = self.client_manager.manager.cli_args.impersonate or impersonate
        if impersonate:
            self.client_manager.check_curl_cffi_is_available()
            if impersonate is True:
                impersonate = "chrome"
            request_params["impersonate"] = impersonate

        else:
            _ = headers.setdefault("User-agent", self.client_manager.manager.config.global_settings.general.user_agent)

        async with self.__request(url, method, request_params, impersonate=bool(impersonate)) as resp:
            exc = None
            try:
                yield await self._check_response(resp, url)
            except Exception as e:
                exc = e
                raise
            finally:
                if self._save_responses_to_disk:
                    _ = self.client_manager.manager.logs.task_group.create_task(
                        asyncio.to_thread(
                            _write_resp_to_disk,
                            self._responses_folder,
                            url,
                            resp,
                            exc,
                        )
                    )

    def __sync_session_cookies(self, url: AbsoluteHttpURL) -> None:
        """
        Apply to the cookies from the `curl` session into the `aiohttp` session, filtering them by the URL

        This is mostly just to get the `cf_cleareance` cookie value into the `aiohttp` session

        The reverse (sync `aiohttp` -> `curl`) is not needed at the moment, so it is skipped
        """
        now = time.time()
        for cookie in self.client_manager._curl_session.cookies.jar:
            simple_cookie = make_simple_cookie(cookie, now)
            self.client_manager.cookies.update_cookies(simple_cookie, url)

    @contextlib.asynccontextmanager
    async def __request(
        self,
        url: AbsoluteHttpURL,
        method: HttpMethod,
        request_params: Mapping[str, Any],
        *,
        impersonate: bool,
    ) -> AsyncGenerator[AbstractResponse[Any]]:
        request_id = str(uuid.uuid4())
        logger.debug(
            "Starting %s request [id=%s] to %s \n%s",
            method,
            request_id,
            url,
            _LazyRequestLog(request_params),
        )
        resp = None
        try:
            if impersonate:
                async with contextlib.aclosing(
                    await self.client_manager._curl_session.request(method, str(url), stream=True, **request_params)
                ) as curl_resp:
                    resp = AbstractResponse.create(curl_resp)
                    yield resp
                    self.__sync_session_cookies(url)

                return

            async with (
                self.client_manager._session.request(method, url, **request_params) as aio_resp,
            ):
                resp = AbstractResponse.create(aio_resp)
                yield resp

        finally:
            if resp is not None:
                logger.debug("Finished %s request [id=%s]\n%s", method, request_id, _LazyResponseLog(resp))

    async def _check_response(self, abs_resp: AbstractResponse[Any], url: AbsoluteHttpURL, data: Any | None = None):
        """Checks the HTTP response status and retries DDOS Guard errors with FlareSolverr.

        Returns an AbstractResponse confirmed to not be a DDOS Guard page."""
        try:
            await self.client_manager.check_http_status(abs_resp)
            return abs_resp
        except DDOSGuardError as e:
            if not (flare := self.client_manager.flaresolverr):
                raise

            try:
                solution = await flare.request(url, data)
            except RuntimeError:
                raise e from None

            self.client_manager.cookies.update_cookies(solution.cookies)
            await _check_flaresolverr_resp(
                self.client_manager.manager.config.global_settings.general.user_agent, solution
            )
            return AbstractResponse.create(solution)


async def _check_flaresolverr_resp(cdl_user_agent: str, solution: flaresolverr.Solution) -> None:
    mismatch_ua_msg = (
        "Config user_agent and flaresolverr user_agent do not match:"
        f"\n  Cyberdrop-DL: '{cdl_user_agent}'"
        f"\n  Flaresolverr: '{solution.user_agent}'"
    )

    try:
        await ddos_guard.check(solution.content)
    except DDOSGuardError:
        if solution.user_agent != cdl_user_agent:
            raise DDOSGuardError(mismatch_ua_msg) from None

    if solution.user_agent != cdl_user_agent:
        logger.warning(f"{mismatch_ua_msg}\n Response was successful but cookies will not be valid")


def _write_resp_to_disk(
    folder: Path,
    url: AbsoluteHttpURL,
    response: AbstractResponse[Any],
    exc: Exception | None = None,
) -> None:

    max_stem_len = 245 - len(str(folder)) + len(constants.STARTUP_TIME_STR) + 10

    log_date = response.created_at.strftime(constants.LOGS_DATETIME_FORMAT)
    path_safe_url = sanitize_filename(Path(str(url)).as_posix().replace("/", "-"))
    filename = f"{path_safe_url[:max_stem_len]}_{log_date}.html"
    file = folder / filename
    content = response.create_report(exc)
    try:
        _ = file.write_text(content, "utf8")
    except OSError:
        pass


class HTTPClientProxy:
    DOMAIN: ClassVar[str]
    _IMPERSONATE: ClassVar[str | bool | None] = None
    client: HTTPClient  # pyright: ignore[reportUninitializedInstanceVariable]

    @classmethod
    def __json_resp_check__(cls, json_resp: Any, resp: AbstractResponse[Any], /) -> None:
        """Custom check for JSON responses.

        This method is called automatically by the `HttpClient` when a JSON response is received from `cls.DOMAIN`
        and it was **NOT** successful (`4xx` or `5xx` HTTP code).

        Override this method in subclasses to raise a custom `ScrapeError` instead of the default HTTP error

        Example:
            ```python
            if isinstance(json, dict) and json.get("status") == "error":
                raise ScrapeError(422, f"API error: {json['message']}")
            ```

        IMPORTANT:
            Cases were the response **IS** successful (200, OK) but the JSON indicates an error
            should be handled by the crawler itself
        """

    @signature.copy(HTTPClient.request)
    @contextlib.asynccontextmanager
    async def request(
        self, *args, impersonate: str | bool | None = None, **kwargs
    ) -> AsyncGenerator[AbstractResponse[Any]]:
        if impersonate is None:
            impersonate = self._IMPERSONATE

        with self.client.client_manager.set_json_checker(self.__json_resp_check__):
            async with (
                self.client._limiter(self.DOMAIN),
                self.client.request(*args, impersonate=impersonate, **kwargs) as resp,
            ):
                yield resp

    @signature.copy(request)
    async def request_json(self, *args, **kwargs) -> Any:
        async with self.request(*args, **kwargs) as resp:
            return await resp.json()

    @signature.copy(request)
    async def request_soup(self, *args, **kwargs) -> BeautifulSoup:
        async with self.request(*args, **kwargs) as resp:
            return await resp.soup()

    @signature.copy(request)
    async def request_text(self, *args, **kwargs) -> str:
        async with self.request(*args, **kwargs) as resp:
            return await resp.text()
