from __future__ import annotations

import mimetypes
import platform
import re
import unicodedata
from contextvars import ContextVar
from pathlib import Path

from cyberdrop_dl.constants import FileExt
from cyberdrop_dl.exceptions import FileNameError, InvalidExtensionError, NoExtensionError, PathTraversalError

_ALLOWED_FILEPATH_PUNCTUATION = " .-_!#$%'()+,;=@[]^{}~"
_SANITIZE_FILENAME_PATTERN = r'[<>:"/\\|?*\']'
_RAR_MULTIPART_PATTERN = r"^part\d+"

MAX_FILE_LEN: ContextVar[int] = ContextVar("_MAX_FILE_LEN", default=95)
MAX_FOLDER_LEN: ContextVar[int] = ContextVar("_MAX_FOLDER_LEN", default=60)


def remove_emojis_and_symbols(filename: str) -> str:
    """Allow all Unicode letters/numbers/marks, plus safe filename punctuation, but not symbols or emoji."""
    return "".join(
        char
        for char in filename
        if (char in _ALLOWED_FILEPATH_PUNCTUATION or unicodedata.category(char)[0] in {"L", "N", "M"})
    ).strip()


def sanitize_filename(name: str, sub: str = "") -> str:
    clean_name = re.sub(_SANITIZE_FILENAME_PATTERN, sub, name).strip()
    if platform.system() in {"Windows", "Darwin"}:
        clean_name = remove_emojis_and_symbols(clean_name)
    path = Path(clean_name)
    return path.stem.strip() + path.suffix


def sanitize_folder(title: str, max_len: int | None = None) -> str:
    max_len = max_len or MAX_FOLDER_LEN.get()
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

    max_len = (max_len or MAX_FILE_LEN.get()) - len(suffix)
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
