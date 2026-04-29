from __future__ import annotations

import contextlib
import dataclasses
import functools
import inspect
import itertools
import logging
import os
import platform
import re
import sys
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Concatenate, ParamSpec, Protocol, Self, TypeVar, cast, overload

import yarl
from aiohttp import ClientConnectorError, TooManyRedirects
from mega.errors import MegaNzError
from pydantic import ValidationError
from typing_extensions import TypeIs

from cyberdrop_dl.constants import TempExt
from cyberdrop_dl.exceptions import (
    CDLBaseError,
    ErrorLogMessage,
    InvalidURLError,
    TooManyCrawlerErrors,
    create_error_msg,
    get_origin,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Generator

    from cyberdrop_dl.downloader.downloader import Downloader
    from cyberdrop_dl.managers.manager import Manager
    from cyberdrop_dl.url_objects import AbsoluteHttpURL, MediaItem, ScrapeItem

    class _HasManager(Protocol):
        manager: Manager

    _HasManagerT = TypeVar("_HasManagerT", bound=_HasManager)
    _Origin = TypeVar("_Origin", bound=ScrapeItem | MediaItem | yarl.URL)

_P = ParamSpec("_P")
_R = TypeVar("_R")


class Dataclass(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Any]]


logger = logging.getLogger(__name__)


_FIELDS_CACHE: dict[type, tuple[str, ...]] = {}


def _fields(cls: type) -> tuple[str, ...]:
    if fields := _FIELDS_CACHE.get(cls):
        return fields
    fields = _FIELDS_CACHE[cls] = tuple(f.name for f in dataclasses.fields(cls))
    return fields


class DictDataclass(Dataclass, Protocol):
    @classmethod
    def filter_dict(cls, data: dict[str, Any], /) -> dict[str, Any]:
        return {name: data.get(name) for name in _fields(cls)}

    @classmethod
    def from_dict(cls, data: dict[str, Any], /, **overrides: Any) -> Self:
        if overrides:
            data.update(overrides)
        return cls(**cls.filter_dict(data))


@contextlib.contextmanager
def error_handling_context(self: _HasManager, item: ScrapeItem | MediaItem | yarl.URL) -> Generator[None]:
    link: yarl.URL = item if isinstance(item, yarl.URL) else item.url
    error_log_msg = origin = exc_info = None
    link_to_show: yarl.URL | str = ""
    is_segment: bool = getattr(item, "is_segment", False)
    is_downloader: bool = bool(getattr(self, "log_prefix", False))
    try:
        yield
    except TooManyCrawlerErrors:
        return
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
    except Exception as e:
        exc_info = e
        error_log_msg = ErrorLogMessage.from_unknown_exc(e)

    if error_log_msg is None or is_segment:
        return

    link_to_show = link_to_show or link
    origin = origin or get_origin(item)
    if is_downloader:
        self, item = cast("Downloader", self), cast("MediaItem", item)
        self.write_download_error(item, error_log_msg, exc_info)
        return

    logger.error(f"Scrape Failed: {link_to_show} ({error_log_msg.main_log_msg})", exc_info=exc_info)
    self.manager.logs.write_scrape_error(link_to_show, error_log_msg.csv_log_msg, origin)
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


def get_download_path(manager: Manager, scrape_item: ScrapeItem, domain: str) -> Path:
    """Returns the path to the download folder."""
    download_dir = manager.config.settings.files.download_folder

    return download_dir / scrape_item.create_download_path(domain)


def _get_size(path: os.DirEntry[str]) -> int | None:
    try:
        return path.stat(follow_symlinks=False).st_size
    except (OSError, ValueError):
        return


def delete_empty_files_and_folders(dirname: Path | str) -> bool:
    """walks and removes in place"""

    has_non_empty_files = False
    has_non_empty_subfolders = False

    try:
        for entry in os.scandir(dirname):
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                is_dir = False
            if is_dir:
                deleted = delete_empty_files_and_folders(entry.path)
                if not deleted:
                    has_non_empty_subfolders = True
            elif _get_size(entry) == 0:
                try:
                    os.unlink(entry)  # noqa: PTH108
                except OSError as e:
                    logger.error(f"Unable to delete '{entry.path}' ({e!r})")
                    has_non_empty_files = True
                else:
                    logger.debug(f"Deleted '{entry.path}'")
            else:
                has_non_empty_files = True

    except OSError:
        logger.exception(f"Unknown error while walking '{dirname}'")
        pass

    if has_non_empty_files or has_non_empty_subfolders:
        return False
    try:
        os.rmdir(dirname)  # noqa: PTH106
        return True
    except OSError:
        return False


def check_partials_and_empty_folders(manager: Manager) -> None:
    download_folder = manager.config.settings.files.download_folder

    _check_for_partial_files(download_folder)
    settings = manager.config.settings.runtime_options
    if settings.delete_partial_files:
        logger.info("Deleting partial downloads...")
        for file in _partial_files(download_folder):
            logger.debug(f"Deleting '{file}'")
            file.unlink(missing_ok=True)

    if settings.skip_check_for_empty_folders:
        return

    logger.info("Deleting empty files and folders...")
    _ = delete_empty_files_and_folders(download_folder)

    sorted_folder = manager.config.settings.sorting.sort_folder
    if sorted_folder and manager.config.settings.sorting.sort_downloads:
        _ = delete_empty_files_and_folders(sorted_folder)


def _partial_files(dir: Path | str) -> Generator[Path]:
    try:
        for entry in os.scandir(dir):
            try:
                if entry.is_dir(follow_symlinks=False):
                    yield from _partial_files(entry.path)
                    continue
            except OSError:
                pass

            suffix = entry.name.rpartition(".")[-1]
            if f".{suffix}" in TempExt:
                yield Path(entry.path)
    except OSError:
        return


def _check_for_partial_files(path: Path) -> None:
    logger.info("Checking for partial downloads...")
    has_partial_files = next(_partial_files(path), None)
    if has_partial_files:
        logger.warning("There are partial downloads in the downloads folder")


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

        if system in ("Linux",):
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


def truncated_preview(content: str, max_len: int = 150) -> str:
    if len(content) <= max_len:
        return content
    return f"{content[:max_len]} ... ({len(content) - max_len:,} chars omitted)"
