from __future__ import annotations

import base64
import contextlib
import functools
import inspect
import itertools
import logging
import platform
import re
import sys
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Concatenate, ParamSpec, Protocol, TypeVar, cast, overload

import yarl
from aiohttp import ClientConnectorError, TooManyRedirects
from mega.errors import MegaNzError
from pydantic import ValidationError
from typing_extensions import TypeIs

from cyberdrop_dl.exceptions import (
    CDLBaseError,
    ErrorLogMessage,
    InvalidURLError,
    TooManyCrawlerErrors,
    create_error_msg,
    get_origin,
)
from cyberdrop_dl.utils._dataclasses import DictDataclass, deserialize, filter_data, type_adapter
from cyberdrop_dl.utils._path_traverse import has_partial_files, partial_files

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Generator
    from pathlib import Path

    from cyberdrop_dl.downloader.http import Downloader
    from cyberdrop_dl.manager import Manager
    from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem, ScrapeItem

    class _HasManager(Protocol):
        manager: Manager

    _HasManagerT = TypeVar("_HasManagerT", bound=_HasManager)
    _Origin = TypeVar("_Origin", bound=ScrapeItem | MediaItem | yarl.URL)

_P = ParamSpec("_P")
_R = TypeVar("_R")
_ = DictDataclass, deserialize, filter_data, type_adapter

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def group_exceptions(message: str | None = None) -> Generator[None]:
    try:
        yield
    except ExceptionGroup as e:
        raise ExceptionGroup(message or _exc_group_msg(e), e.exceptions) from None


def _exc_group_msg(e: ExceptionGroup) -> str:
    if "unhandled errors in a TaskGroup" not in e.message:
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
    except TooManyCrawlerErrors:
        return
    except ExceptionGroup as e:
        error_log_msg = ErrorLogMessage(_exc_group_msg(e), str(e))
        exc_info = e.with_traceback(None)
    except CDLBaseError as e:
        error_log_msg = ErrorLogMessage(e.ui_failure, str(e))
        origin = e.origin
        link_to_show = getattr(e, "url", None) or link_to_show
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
                -9: HTTPStatus.GONE,
                -16: HTTPStatus.FORBIDDEN,
                -24: 509,
                -401: 509,
            }.get(code):
                ui_failure = create_error_msg(http_code)
            else:
                ui_failure = f"MegaNZ Error [{code}]"
        else:
            ui_failure = "MegaNZ Error"

        error_log_msg = ErrorLogMessage(ui_failure, str(e))

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
    exc_info: Exception | None,
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
def error_handling_wrapper(
    func: Callable[Concatenate[_HasManagerT, _Origin, _P], _R],
) -> Callable[Concatenate[_HasManagerT, _Origin, _P], _R]: ...


@overload
def error_handling_wrapper(
    func: Callable[Concatenate[_HasManagerT, _Origin, _P], Coroutine[None, None, _R]],
) -> Callable[Concatenate[_HasManagerT, _Origin, _P], Coroutine[None, None, _R]]: ...


def error_handling_wrapper(
    func: Callable[Concatenate[_HasManagerT, _Origin, _P], _R | Coroutine[None, None, _R]],
) -> Callable[Concatenate[_HasManagerT, _Origin, _P], _R | Coroutine[None, None, _R]]:
    """Wrapper handles errors for url scraping."""

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(self: _HasManagerT, item: _Origin, *args: _P.args, **kwargs: _P.kwargs) -> _R:
            with error_handling_context(self, item):
                return await func(self, item, *args, **kwargs)

        return async_wrapper

    @functools.wraps(func)
    def wrapper(self: _HasManagerT, item: _Origin, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        with error_handling_context(self, item):
            result = func(self, item, *args, **kwargs)
            assert not inspect.isawaitable(result)
            return result

    return wrapper


def delete_empty_files_and_folders(path: Path) -> None:
    """walks and removes in place"""

    from cyberdrop_dl.utils._path_traverse import delete_empty_files_and_folders_in_place

    if not path.is_dir():
        return
    _ = delete_empty_files_and_folders_in_place(path)


def check_partials_and_empty_folders(manager: Manager) -> None:
    download_folder = manager.config.settings.files.download_folder

    logger.info("Checking for partial downloads...")
    if has_partial_files(download_folder):
        logger.warning("There are partial downloads in the downloads folder")

    settings = manager.config.settings.runtime_options
    if settings.delete_partial_files:
        logger.info("Deleting partial downloads...")
        delete_partial_files(download_folder)

    if settings.skip_check_for_empty_folders:
        return

    logger.info("Deleting empty files and folders...")
    delete_empty_files_and_folders(download_folder)

    sorted_folder = manager.config.settings.sorting.sort_folder
    if sorted_folder and manager.config.settings.sorting.sort_downloads:
        delete_empty_files_and_folders(sorted_folder)


def delete_partial_files(path: Path) -> None:
    for file in partial_files(path):
        try:
            file.unlink()
        except OSError as e:
            logger.error(f"Unable to delete '{file}' ({e!r})")
        else:
            logger.debug(f"Deleted '{file}'")


def extr_text(text: str, /, start: str, end: str) -> str:
    """Extracts the text between two strings in a larger text. Result will be stripped"""
    start_index = text.index(start) + len(start)
    end_index = text.index(end, start_index)
    return text[start_index:end_index].strip()


def _str_to_url(link_str: str) -> yarl.URL:
    if not link_str:
        raise InvalidURLError("link_str is empty", url=link_str)

    def fix_query_params_encoding(link: str) -> str:
        if "?" not in link:
            return link
        parts, query_and_frag = link.split("?", 1)
        query_and_frag = query_and_frag.replace("+", "%20")
        return f"{parts}?{query_and_frag}"

    def fix_multiple_slashes(link_str: str) -> str:
        return re.sub(r"(?:https?)?:?(\/{3,})", "//", link_str)

    try:
        clean_link_str = fix_multiple_slashes(fix_query_params_encoding(link_str))
        return yarl.URL(clean_link_str, encoded="%" in clean_link_str)

    except (AttributeError, ValueError, TypeError) as e:
        raise InvalidURLError(str(e), url=link_str) from e


def parse_url(
    link_str: AbsoluteHttpURL | yarl.URL | str, relative_to: AbsoluteHttpURL | None = None, *, trim: bool = True
) -> AbsoluteHttpURL:
    """Parse a string into an absolute URL, handling relative URLs, encoding and optionally removes trailing slash (trimming).
    Raises:
        InvalidURLError: If the input string is not a valid URL or if any other error occurs during parsing.
        TypeError: If `relative_to` is `None` and the parsed URL is relative or has no scheme.
    """

    url = _str_to_url(link_str) if isinstance(link_str, str) else link_str
    if not url.absolute:
        if not relative_to:
            raise InvalidURLError("Relative URL with no known base", url=link_str)
        url = relative_to.join(url)
    if not url.scheme:
        url = url.with_scheme(relative_to.scheme if relative_to else "https")
    assert is_absolute_http_url(url)
    if not trim:
        return url
    return remove_trailing_slash(url)


def is_absolute_http_url(url: yarl.URL) -> TypeIs[AbsoluteHttpURL]:
    return url.absolute and url.scheme.startswith("http")


def remove_trailing_slash(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    if url.name or url.path == "/":
        return url
    return url.parent.with_fragment(url.fragment).with_query(url.query)


def get_system_information() -> dict[str, Any]:

    def get_common_name() -> str:
        system = platform.system()

        if system == "Linux":
            try:
                return platform.freedesktop_os_release()["PRETTY_NAME"]
            except OSError:
                pass

        if system == "Android" and sys.version_info >= (3, 13):
            ver = platform.android_ver()
            os_name = f"{system} {ver.release}"
            for component in (ver.manufacturer, ver.model, ver.device):
                if component:
                    os_name += f" ({component})"
            return os_name

        default = platform.platform(aliased=True, terse=True).replace("-", " ")
        if system == "Windows" and (edition := platform.win32_edition()):
            return f"{default} {edition}"
        return default

    system_info = (
        {
            "prefix": sys.prefix,
            "executable": sys.executable,
            "GIL enabled": sys._is_gil_enabled() if sys.version_info >= (3, 13) else True,
        }
        | platform.uname()._asdict()
        | {
            "architecture": str(platform.architecture()),
            "python": f"{platform.python_version()} {platform.python_implementation()}",
            "common_name": get_common_name(),
        }
    )
    _ = system_info.pop("node", None)
    return system_info


def is_blob_or_svg(link: str) -> bool:
    return link.startswith(("data:", "blob:", "javascript:"))


def xor_decrypt(encrypted_data: bytes, key: bytes) -> str:
    data = bytearray(b_input ^ b_key for b_input, b_key in zip(encrypted_data, itertools.cycle(key)))
    return data.decode("utf-8", errors="ignore")


def truncated_preview(content: str, max_len: int = 100) -> str:
    if len(content) <= max_len:
        return content
    return f"{content[:max_len]} ... ({len(content) - max_len:,} chars omitted)"


def basic_auth(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return f"Basic {token}"
