from __future__ import annotations

import base64
import itertools
import logging
import platform
import sys
from typing import TYPE_CHECKING, Any

from cyberdrop_dl.utils._dataclasses import DictDataclass, deserialize, filter_data, type_adapter  # noqa: F401
from cyberdrop_dl.utils._errors import error_handling_context, error_handling_wrapper  # noqa: F401
from cyberdrop_dl.utils._path_traverse import has_partial_files, partial_files
from cyberdrop_dl.utils._url import is_absolute_http_url, remove_trailing_slash  # noqa: F401
from cyberdrop_dl.utils._url import parse_http_url as parse_url  # noqa: F401

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from pathlib import Path

    from cyberdrop_dl.config import Config


logger = logging.getLogger(__name__)


def delete_empty_files_and_folders(path: Path) -> None:
    """walks and removes in place"""

    from cyberdrop_dl.logs import MAIN_LOG_FILE
    from cyberdrop_dl.utils._path_traverse import delete_empty_files_and_folders_in_place

    if not path.is_dir():
        return

    _ = delete_empty_files_and_folders_in_place(path, exclude=[MAIN_LOG_FILE.get(None)])


def check_partials_and_empty_folders(config: Config) -> None:
    download_folder = config.settings.files.download_folder

    logger.info("Checking for partial downloads...")
    if has_partial_files(download_folder):
        logger.warning("There are partial downloads in the downloads folder")

    settings = config.settings.runtime_options
    if settings.delete_partial_files:
        logger.info("Deleting partial downloads...")
        delete_partial_files(download_folder)

    if settings.skip_check_for_empty_folders:
        return

    logger.info("Deleting empty files and folders...")
    delete_empty_files_and_folders(download_folder)

    sorted_folder = config.settings.sorting.sort_folder
    if sorted_folder and config.settings.sorting.sort_downloads:
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


def unique[T](itr: Iterable[T], /) -> Generator[T]:
    seen: set[T] = set()
    for ele in itr:
        if ele not in seen:
            seen.add(ele)
            yield ele
