from __future__ import annotations

import contextlib
import functools
import inspect
import logging
from http import HTTPStatus
from typing import TYPE_CHECKING, Concatenate, Protocol, cast, overload

import aiohttp.client_exceptions
import mega.errors
import yarl
from curl_cffi.requests import exceptions as curl_exceptions
from pydantic import ValidationError

from cyberdrop_dl.exceptions import CDLAppError, CDLBaseError, create_error_msg, get_origin

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Generator
    from pathlib import Path

    from cyberdrop_dl.downloader.http import Downloader
    from cyberdrop_dl.manager import Manager
    from cyberdrop_dl.url_objects import MediaItem, ScrapeItem

    class _HasManager(Protocol):
        manager: Manager


logger = logging.getLogger(__name__)

_ERROR_WRAPPER_ATTR = "__cdl_error_wrapped__"


def is_error_wrapped(method: object) -> bool:
    return getattr(method, _ERROR_WRAPPER_ATTR, False)


def _mark_as_safe[T](fn: T) -> T:
    setattr(fn, _ERROR_WRAPPER_ATTR, True)
    return fn


def _clean_curl_error(e: object) -> str:
    return str(e).partition(". See https://curl.se/")[0]


@contextlib.contextmanager
def _curl_context() -> Generator[None]:
    try:
        yield
    except curl_exceptions.Timeout as e:
        log_msg = _clean_curl_error(repr(e))
        raise CDLAppError("Timeout", log_msg) from None
    except curl_exceptions.DNSError as e:
        log_msg = _clean_curl_error(repr(e))
        raise CDLAppError("Client Connector Error", log_msg) from None
    except curl_exceptions.RequestException as e:
        log_msg = _clean_curl_error(e)
        raise CDLAppError(f"Curl Error ({e.code})", log_msg) from None


@contextlib.contextmanager
def _aiohttp_context() -> Generator[None]:
    try:
        yield
    except aiohttp.client_exceptions.TooManyRedirects as e:
        ui_failure = "Too Many Redirects"
        info = {
            "url": str(e.request_info.real_url),
            "history": tuple(str(r.real_url) for r in e.history),
        }
        raise CDLAppError(ui_failure, f"{ui_failure}\n{info}") from None
    except aiohttp.client_exceptions.ClientConnectorError as e:
        raise CDLAppError("Client Connector Error", str(e)) from None


@contextlib.contextmanager
def _exc_group_context() -> Generator[None]:
    try:
        yield
    except ExceptionGroup as e:
        if e.message and "unhandled errors in a TaskGroup" not in e.message:
            msg = e.message
        else:
            first = e.exceptions[0]
            msg = getattr(first, "ui_failure", None) or str(first)
        raise CDLAppError(msg, str(e)) from e.with_traceback(None)


_MEGA_HTTP_CODES = Final = {
    -4: HTTPStatus.TOO_MANY_REQUESTS,
    -8: HTTPStatus.GONE,
    -9: HTTPStatus.GONE,
    -16: HTTPStatus.FORBIDDEN,
    -17: 509,
    -24: 509,
    -401: 509,
}


@contextlib.contextmanager
def _mega_nz_context() -> Generator[None]:
    try:
        yield
    except mega.errors.RequestError as e:
        if e.code and (http_code := _MEGA_HTTP_CODES.get(e.code)):
            ui_failure = create_error_msg(http_code)
        else:
            ui_failure = f"MegaNZ Error [{e.code}]"

        raise CDLAppError(ui_failure, f"{ui_failure} {e.message}") from None

    except mega.errors.MegaNzError as e:
        raise CDLAppError("MegaNZ Error", str(e)) from None


@contextlib.contextmanager
def _pydantic_context() -> Generator[None]:
    try:
        yield
    except ValidationError as e:
        ui_failure = create_error_msg(422)
        log_msg = str(e).partition("For further information")[0].strip()
        raise CDLAppError(ui_failure, log_msg) from e


@contextlib.contextmanager
def _builtin_context() -> Generator[None]:
    try:
        yield
    except NotImplementedError as e:
        raise CDLAppError("NotImplemented") from e
    except TimeoutError as e:
        raise CDLAppError("Timeout", repr(e)) from None


@contextlib.contextmanager
def error_handling_context(self: _HasManager, item: ScrapeItem | MediaItem | yarl.URL) -> Generator[None]:
    if getattr(item, "is_segment", False):
        with contextlib.suppress(Exception):
            yield
        return

    url: yarl.URL = item if type(item) is yarl.URL else item.url  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
    app_error = origin = exc = None
    real_url: yarl.URL | str = ""
    try:
        with (
            _builtin_context(),
            _pydantic_context(),
            _aiohttp_context(),
            _curl_context(),
            _mega_nz_context(),
            _exc_group_context(),
        ):
            yield

    except CDLBaseError as e:
        app_error = CDLAppError(e.ui_failure, str(e))
        origin = e.origin
        real_url = getattr(e, "url", None) or real_url
        exc = e.__cause__
    except CDLAppError as e:
        app_error = e
        exc = e.__cause__
    except Exception as e:  # noqa: BLE001
        exc = e
        app_error = CDLAppError.from_unknown_exc(e)

    if app_error is None:
        return

    _log_error(self, real_url or url, item, app_error, exc, origin)


def _log_error(  # noqa: PLR0913
    self: _HasManager,
    url: yarl.URL | str,
    item: ScrapeItem | MediaItem | yarl.URL,
    app_error: CDLAppError,
    exc: BaseException | None,
    origin: yarl.URL | Path | None,
) -> None:
    origin = origin or get_origin(item)
    is_downloader = bool(getattr(self, "log_prefix", False))
    if is_downloader:
        self, item = cast("Downloader", self), cast("MediaItem", item)
        logger.error(
            f"{self.log_prefix} Failed: {item.url} ({app_error.msg}) \n -> Referer: {item.referer}",
            exc_info=exc,
        )
        self.manager.logs.write_download_error(item.url, item.referer, app_error.csv_msg, origin)
        self.manager.scrape_mapper.tui.files.stats.failed += 1
        self.manager.scrape_mapper.tui.download_errors.add(app_error.ui_error)
        return

    logger.error(f"Scrape Failed: {url} ({app_error.msg})", exc_info=exc)
    self.manager.logs.write_scrape_error(url, app_error.csv_msg, origin)
    self.manager.scrape_mapper.tui.scrape_errors.add(app_error.ui_error)


@overload
def error_handling_wrapper[HasManagerT: _HasManager, Origin: ScrapeItem | MediaItem | yarl.URL, **P, R](
    func: Callable[Concatenate[HasManagerT, Origin, P], R],
) -> Callable[Concatenate[HasManagerT, Origin, P], R]: ...


@overload
def error_handling_wrapper[HasManagerT: _HasManager, Origin: ScrapeItem | MediaItem | yarl.URL, **P, R](
    func: Callable[Concatenate[HasManagerT, Origin, P], Coroutine[None, None, R]],
) -> Callable[Concatenate[HasManagerT, Origin, P], Coroutine[None, None, R]]: ...


def error_handling_wrapper[HasManagerT: _HasManager, Origin: ScrapeItem | MediaItem | yarl.URL, **P, R](
    func: Callable[Concatenate[HasManagerT, Origin, P], R | Coroutine[None, None, R]],
) -> Callable[Concatenate[HasManagerT, Origin, P], R | Coroutine[None, None, R]]:
    """Wrapper handles errors for url scraping."""

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(self: HasManagerT, item: Origin, *args: P.args, **kwargs: P.kwargs) -> R:
            with error_handling_context(self, item):
                return await func(self, item, *args, **kwargs)

        return _mark_as_safe(async_wrapper)

    @functools.wraps(func)
    def wrapper(self: HasManagerT, item: Origin, *args: P.args, **kwargs: P.kwargs) -> R:
        with error_handling_context(self, item):
            result = func(self, item, *args, **kwargs)
            assert not inspect.isawaitable(result)
            return result

    return _mark_as_safe(wrapper)
