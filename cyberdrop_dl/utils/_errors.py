from __future__ import annotations

import contextlib
import functools
import inspect
import logging
from http import HTTPStatus
from typing import TYPE_CHECKING, Concatenate, Protocol, cast, overload

import yarl
from aiohttp import ClientConnectorError, TooManyRedirects
from mega.errors import MegaNzError
from pydantic import ValidationError

from cyberdrop_dl.exceptions import CDLBaseError, ErrorLogMessage, create_error_msg, get_origin

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


@contextlib.contextmanager
def group_exceptions(message: str | None = None) -> Generator[None]:
    try:
        yield
    except ExceptionGroup as e:
        raise ExceptionGroup(message or _exc_group_msg(e), e.exceptions) from None


def _exc_group_msg(e: ExceptionGroup) -> str:
    if e.message and "unhandled errors in a TaskGroup" not in e.message:
        return e.message

    first = e.exceptions[0]
    return getattr(first, "ui_failure", None) or str(first)


@contextlib.contextmanager
def error_handling_context(self: _HasManager, item: ScrapeItem | MediaItem | yarl.URL) -> Generator[None]:  # noqa: C901, PLR0912
    link: yarl.URL = item if isinstance(item, yarl.URL) else item.url
    error_log_msg = origin = exc_info = None
    link_to_show: yarl.URL | str = ""
    is_segment: bool = getattr(item, "is_segment", False)
    try:
        with group_exceptions():
            yield
    except ExceptionGroup as e:
        error_log_msg = ErrorLogMessage(_exc_group_msg(e), str(e))
        exc_info = e.with_traceback(None)
    except CDLBaseError as e:
        error_log_msg = ErrorLogMessage(e.ui_failure, str(e))
        origin = e.origin
        link_to_show = getattr(e, "url", None) or link_to_show
        exc_info = e.__cause__
    except NotImplementedError as e:
        error_log_msg = ErrorLogMessage("NotImplemented")
        exc_info = e
    except TooManyRedirects as e:
        ui_failure = "Too Many Redirects"
        info = {
            "url": str(e.request_info.real_url),
            "history": tuple(str(r.real_url) for r in e.history),
        }
        error_log_msg = ErrorLogMessage(ui_failure, f"{ui_failure}\n{info}")
    except MegaNzError as e:
        if code := getattr(e, "code", None):
            if http_code := {
                -4: HTTPStatus.TOO_MANY_REQUESTS,
                -8: HTTPStatus.GONE,
                -9: HTTPStatus.GONE,
                -16: HTTPStatus.FORBIDDEN,
                -17: 509,
                -24: 509,
                -401: 509,
            }.get(code):
                ui_failure = create_error_msg(http_code)
            else:
                ui_failure = f"MegaNZ Error [{code}]"
        else:
            ui_failure = "MegaNZ Error"

        error_log_msg = ErrorLogMessage(ui_failure, f"{ui_failure} {e!s}")

    except TimeoutError as e:
        error_log_msg = ErrorLogMessage("Timeout", repr(e))
    except ClientConnectorError as e:
        ui_failure = "Client Connector Error"
        suffix = "" if (link.host or "").startswith(e.host) else f" from {link}"
        log_msg = f"{e}{suffix}. If you're using a VPN, try turning it off"
        error_log_msg = ErrorLogMessage(ui_failure, log_msg)
    except ValidationError as e:
        exc_info = e
        ui_failure = create_error_msg(422)
        log_msg = str(e).partition("For further information")[0].strip()
        error_log_msg = ErrorLogMessage(ui_failure, log_msg)
    except Exception as e:  # noqa: BLE001
        exc_info = e
        error_log_msg = ErrorLogMessage.from_unknown_exc(e)

    if error_log_msg is None or is_segment:
        return

    _log_error(self, link_to_show or link, item, error_log_msg, exc_info, origin)


def _log_error(  # noqa: PLR0913
    self: _HasManager,
    link_to_show: yarl.URL | str,
    item: ScrapeItem | MediaItem | yarl.URL,
    error_log_msg: ErrorLogMessage,
    exc_info: BaseException | None,
    origin: ScrapeItem | MediaItem | yarl.URL | Path | None,
) -> None:
    origin = origin or get_origin(item)
    is_downloader = bool(getattr(self, "log_prefix", False))
    if is_downloader:
        self, item = cast("Downloader", self), cast("MediaItem", item)
        logger.error(
            f"{self.log_prefix} Failed: {item.url} ({error_log_msg.main_log_msg}) \n -> Referer: {item.referer}",
            exc_info=exc_info,
        )
        self.manager.logs.write_download_error(item, error_log_msg.csv_log_msg)
        self.manager.scrape_mapper.tui.files.stats.failed += 1
        self.manager.scrape_mapper.tui.download_errors.add(error_log_msg.ui_failure)
        return

    logger.error(f"Scrape Failed: {link_to_show} ({error_log_msg.main_log_msg})", exc_info=exc_info)
    self.manager.logs.write_scrape_error(link_to_show, error_log_msg.csv_log_msg, origin)  # pyright: ignore[reportArgumentType]
    self.manager.scrape_mapper.tui.scrape_errors.add(error_log_msg.ui_failure)


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
