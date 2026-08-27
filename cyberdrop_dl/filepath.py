from __future__ import annotations

import mimetypes
import platform
import re
import unicodedata
from contextvars import ContextVar
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Self

from cyberdrop_dl.constants import FileExt
from cyberdrop_dl.exceptions import FileNameError, InvalidExtensionError, NoExtensionError, PathTraversalError
from cyberdrop_dl.signature import simple_repr

if TYPE_CHECKING:
    from collections.abc import Callable

type PathOptions = Literal["unix", "windows", "no_emoji", "ascii"]

_ALLOWED_UNICODE_SYMBOLS_AND_PUNCTUATION = " .-_!#$%'()+,;=@[]^{}~"
_RAR_MULTIPART_PATTERN = r"^part\d+"
_MAX_FILE_LEN: ContextVar[int] = ContextVar("_MAX_FILE_LEN", default=95)
_MAX_FOLDER_LEN: ContextVar[int] = ContextVar("_MAX_FOLDER_LEN", default=60)
_PATH_SANITIZER: ContextVar[PathSanitizer] = ContextVar("_PATH_SANITIZER")


class RestrictPath(StrEnum):
    ASCII = "^0-9A-Za-z_."
    WINDOWS = r'<>:"/\\|?*\''
    UNIX = "/"


class UnicodeCategory(StrEnum):
    CONTROL = "C"
    LETTER = "L"
    MARK = "M"
    NUMBER = "N"
    PUNCTUATION = "P"
    SIMBOL = "S"
    SEPARATOR = "Z"


class PathSanitizer:
    def __init__(self, banned_chars: str | None = None, *post_process: Callable[[str], str]) -> None:
        self.banned_chars: str | None = banned_chars
        self.post_process: tuple[Callable[[str], str], ...] = post_process

    __repr__ = simple_repr("banned_chars", "post_process")

    def __call__(self, name: str, repl: str = "") -> str:
        if self.banned_chars:
            name = re.sub(f"[{self.banned_chars}]", repl, name).strip()
        for fn in self.post_process:
            name = fn(name)

        return name

    def __or__(self, other: Self) -> Self:
        return type(self)(self.banned_chars, *self.post_process, other)

    @classmethod
    def v9_default(cls) -> Self:
        if platform.system() in {"Windows", "Darwin"}:
            return cls(RestrictPath.WINDOWS, remove_emojis_and_symbols)
        return cls(RestrictPath.WINDOWS)


def _is_allowed_unicode(char: str) -> bool:
    return char in _ALLOWED_UNICODE_SYMBOLS_AND_PUNCTUATION or unicodedata.category(char)[0] in {
        UnicodeCategory.LETTER,
        UnicodeCategory.NUMBER,
        UnicodeCategory.MARK,
    }


def remove_emojis_and_symbols(filename: str) -> str:
    """Allow all Unicode letters/numbers/marks, plus safe filename punctuation, but not symbols (emojis)."""
    return "".join(filter(_is_allowed_unicode, filename)).strip()


def sanitize_filename(name: str, sub: str = "") -> str:
    try:
        clean = _PATH_SANITIZER.get()
    except LookupError:
        clean = PathSanitizer.v9_default()
        _PATH_SANITIZER.set(clean)

    path = Path(clean(name, sub))
    return path.stem.strip() + path.suffix


def sanitize_folder(title: str, max_len: int | None = None) -> str:
    max_len = max_len or _MAX_FOLDER_LEN.get()
    title = title.replace("\n", "").replace("\t", "").strip()
    title = sanitize_filename(re.sub(r" +", " ", title), "-")
    title = re.sub(r"\.{2,}", ".", title).rstrip(".").strip()

    if all(char in title for char in ("(", ")")):
        new_title, domain_part = title.rsplit("(", 1)
        new_title = _truncate_text(new_title, max_len)
        return f"{new_title} ({domain_part.strip()}"

    return _truncate_text(title, max_len)


def _truncate_text(text: str, max_bytes: int) -> str:
    str_bytes = text.encode("utf-8")[:max_bytes]
    return str_bytes.decode("utf-8", "ignore").strip()


def get_filename_and_ext(
    filename: str,
    /,
    mime_type: str | None = None,
    *,
    xenforo: bool = False,
    max_len: int | None = None,
) -> tuple[str, str]:
    filename_as_path = Path(remove_os_sep(filename))

    if not filename_as_path.suffix:
        if mime_type and (ext := mimetypes.guess_extension(mime_type)):
            filename_as_path = filename_as_path.with_suffix(ext)
        else:
            raise NoExtensionError(filename)

    if xenforo and "-" in filename and filename_as_path.suffix.lstrip(".").isdigit():
        name, _, ext = filename_as_path.name.rpartition("-")
        ext = "." + ext.rsplit(".")[0]
        filename = f"{name}{ext}"
        if ext.lower() not in FileExt.MEDIA:
            raise InvalidExtensionError(filename)

        filename_as_path = Path(filename)

    if len(filename_as_path.suffix) > 5:
        raise InvalidExtensionError(str(filename_as_path))

    filename_as_path = Path(compose_filename(filename_as_path.stem, filename_as_path.suffix, max_len=max_len))
    return filename_as_path.name, filename_as_path.suffix


def remove_os_sep(filename: str) -> str:
    return Path(filename).as_posix().replace("/", "-")


def compose_filename(name: str, suffix: str, *extras: str, max_len: int | None = None) -> str:
    assert suffix.startswith(".")
    name = sanitize_filename(remove_os_sep(name)).removesuffix(suffix)

    max_len = (max_len or _MAX_FILE_LEN.get()) - len(suffix)
    if extras:
        extra_info = sanitize_filename("".join(f"[{info}]" for info in extras))
        if (new_max_len := max_len - len(extra_info) - 1) > 0:
            truncated_stem = f"{_truncate_text(name, new_max_len)} {extra_info}"
        else:
            truncated_stem = _truncate_text(f"{name} {extra_info}", max_len)

    else:
        truncated_stem = _truncate_text(name, max_len)

    return f"{truncated_stem}{suffix.lower()}"


def remove_file_id(filename: str, ext: str) -> str:
    """Removes the additional string some websites adds to the end of every filename."""

    filename = filename.rsplit(ext, 1)[0].rsplit("-", 1)[0]
    tail_no_dot = filename.rsplit("-", 1)[-1]
    ext_no_dot = ext.rsplit(".", 1)[-1]
    tail = f".{tail_no_dot}"
    if re.match(_RAR_MULTIPART_PATTERN, tail_no_dot) and ext == ".rar" and "-" in filename:
        filename, part = filename.rsplit("-", 1)
        filename = f"{filename}.{part}"
    elif ext_no_dot.isdigit() and tail in FileExt.SEVEN_Z and "-" in filename:
        filename, _7z_ext = filename.rsplit("-", 1)
        filename = f"{filename}.{_7z_ext}"
    if not filename.endswith(ext):
        filename += ext
    return filename


def check_path_traversal(download_folder: Path, folder: Path) -> None:
    parts = folder.parts
    if "." in parts or ".." in parts:
        raise PathTraversalError(folder)

    if not folder.resolve().is_relative_to(download_folder):
        raise PathTraversalError(folder)


def check_dangerous_filename(filename: str) -> None:
    if filename.startswith("."):
        raise FileNameError("Dot file", message=f"Dot files are restricted: {filename}")

    path = Path(filename)
    if "\\" in filename or "/" in filename or path.name != filename or path.suffix.lower() in FileExt.DANGEROUS:
        raise FileNameError("Dangerous File Extension", message=filename)


def setup(
    max_file_len: int,
    max_folder_len: int,
    restrict_path: tuple[PathOptions, ...],
) -> None:
    _MAX_FILE_LEN.set(max_file_len)
    _MAX_FOLDER_LEN.set(max_folder_len)

    if not restrict_path:
        return

    sanitizer = PathSanitizer()
    for name in restrict_path:
        other = (
            PathSanitizer(None, remove_emojis_and_symbols)
            if name == "no_emoji"
            else PathSanitizer(RestrictPath[name.upper()])
        )
        sanitizer = sanitizer | other

    _PATH_SANITIZER.set(sanitizer)
