from __future__ import annotations

import dataclasses
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, final

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Sequence

    import yarl
    from yaml import YAMLError


class HasParents(Protocol):
    @property
    def parents(self) -> Sequence[yarl.URL]: ...


class MediaItemLike(HasParents, Protocol):
    @property
    def uploaded_at_date(self) -> dt.datetime | None: ...
    @property
    def ext(self) -> str: ...
    @property
    def duration(self) -> float | None: ...


def _format_error(ui_failure: str, message: str, notes: Sequence[str] | None = None) -> str:
    return append_notes(message if ui_failure == message else f"{ui_failure} - {message}", notes)


# See: https://developers.cloudflare.com/support/troubleshooting/cloudflare-errors/troubleshooting-cloudflare-5xx-errors/
CLOUDFLARE_HTTP_ERROR_CODES = {
    520: "Unexpected Response",
    521: "Web Server Down",
    522: "Connection Timeout",
    523: "Origin Is Unreachable",
    524: "Response Timeout",
    525: "SSL Handshake Failed",
    526: "Untrusted",
    530: "IP Banned / Restricted",
}

# https://en.wikipedia.org/wiki/List_of_HTTP_status_codes#Nonstandard_codes
# Not all of them, just the ones we actually expect to see and do not shadow standard ones
NON_STANDARD_HTTP_ERROR_CODES = {
    419: "Page Expired",
    509: "Bandwidth Limit Exceeded",
    999: "Timeout",
}

HTTP_ERROR_CODES = {
    **NON_STANDARD_HTTP_ERROR_CODES,
    **CLOUDFLARE_HTTP_ERROR_CODES,
    **{code.value: code.phrase for code in HTTPStatus},
}


def _notes(e: BaseException) -> list[str] | tuple[()]:
    return getattr(e, "__notes__", ())


def append_notes(msg: str, notes: Sequence[str] | None = None) -> str:
    if notes:
        return msg + "\n" + "\n".join(f"[NOTE]: {note}" for note in notes)
    return msg


class DatabaseError(RuntimeError): ...


class CDLBaseError(Exception):
    """Base exception for cyberdrop-dl errors."""

    UI_MSG: str = "Something went wrong"
    DEFAULT_MSG: str | None = None

    def __init__(
        self,
        ui_failure: str | None = None,
        message: str | None = None,
        status: str | int | None = None,
        origin: HasParents | yarl.URL | Path | None = None,
    ) -> None:
        self.ui_failure: str = ui_failure or self.UI_MSG
        self.message: str = message or self.DEFAULT_MSG or self.ui_failure
        self.origin: Path | yarl.URL | None = get_origin(origin)
        super().__init__(self.message)
        if status:
            self.status: str | int | None = status
            super().__init__(self.status)

    def __str__(self) -> str:
        return _format_error(self.ui_failure, self.message, _notes(self))

    @classmethod
    def group(cls, errors: tuple[Exception, ...], ui_failure: str | None = None) -> BaseExceptionGroup:
        return BaseExceptionGroup(ui_failure or cls.UI_MSG, errors)


class _UIError(CDLBaseError):
    def __init__(
        self,
        message: str | None = None,
        status: str | int | None = None,
        origin: HasParents | yarl.URL | Path | None = None,
    ):
        super().__init__(self.UI_MSG, message=message or self.DEFAULT_MSG, status=status, origin=origin)


class FlaresolverrError(_UIError):
    UI_MSG: str = "Flaresolverr Error"


class InvalidContentTypeError(_UIError):
    UI_MSG: str = "Invalid Content Type"


class FileNameError(CDLBaseError):
    def __str__(self) -> str:
        return append_notes(f"{self.ui_failure} ({self.message})", _notes(self))


class NoExtensionError(FileNameError):
    UI_MSG: str = "No File Extension"

    def __init__(self, filename: str | None = None, *, origin: HasParents | yarl.URL | None = None) -> None:
        super().__init__(self.UI_MSG, message=filename, origin=origin)


class InvalidExtensionError(NoExtensionError):
    UI_MSG: str = "Invalid File Extension"


class PathTraversalError(CDLBaseError):
    UI_MSG: str = "Path Traversal"

    def __init__(self, path: Path) -> None:
        msg = f"Download path '{path}' is outside destination download path"
        super().__init__(self.UI_MSG, message=msg)


class PasswordProtectedError(_UIError):
    UI_MSG: str = "Password Protected"
    DEFAULT_MSG: str | None = "File/Folder is password protected"


class MaxChildrenError(_UIError):
    UI_MSG: str = "Max Children Reached"
    DEFAULT_MSG: str | None = "Max number of children reached"


class DDOSGuardError(_UIError):
    UI_MSG: str = "DDoS-Guard"
    DEFAULT_MSG: str | None = "DDoS-Guard detected"


class CloudflareBlockedError(DDOSGuardError):
    UI_MSG: str = "Cloudflare Blocked"
    DEFAULT_MSG: str | None = "Cloudflare blocked the request"


class DownloadError(CDLBaseError):
    def __init__(
        self,
        status: str | int,
        message: str | None = None,
        origin: HasParents | yarl.URL | None = None,
        *,
        retry: bool = False,
    ) -> None:
        """This error will be thrown when a download fails."""
        ui_failure = create_error_msg(status)
        msg = message
        self.retry: bool = retry
        super().__init__(ui_failure, message=msg, status=status, origin=origin)


class SlowDownloadError(DownloadError):
    UI_MSG: str = "Slow Download"

    def __init__(self, origin: HasParents | yarl.URL | None = None) -> None:
        """This error will be thrown when a file will be skipped do to a low download speed."""
        super().__init__(self.UI_MSG, origin=origin)


class InsufficientFreeSpaceError(_UIError):
    UI_MSG: str = "Insufficient Free Space"


class SkipDownloadError(_UIError):
    """Throw this when a download is not allowed by config options"""


class RestrictedFiletypeError(SkipDownloadError):
    UI_MSG: str = "Restricted File Ext"

    def __init__(self, origin: MediaItemLike) -> None:
        """This error will be thrown when has a filetype not allowed by config."""
        message = f"File extension ({origin.ext}) ignored by config options"
        super().__init__(message=message, origin=origin)


class DurationError(SkipDownloadError):
    UI_MSG: str = "Duration Not Allowed"

    def __init__(self, origin: MediaItemLike) -> None:
        """This error will be thrown when the file duration is not allowed by the config."""
        message = f"File duration ({origin.duration}s) out of config range"
        super().__init__(message=message, origin=origin)


class RestrictedDateRangeError(SkipDownloadError):
    UI_MSG: str = "Restricted DateRange"

    def __init__(self, origin: MediaItemLike) -> None:
        """This error will be thrown when the publication date of the media item is not allowed by config."""
        message = f"File upload date ({origin.uploaded_at_date}s) out of config range"
        super().__init__(message=message, origin=origin)


class ScrapeError(CDLBaseError):
    def __init__(
        self, status: str | int, message: str | None = None, origin: HasParents | yarl.URL | None = None
    ) -> None:
        """This error will be thrown when a scrape fails."""
        ui_failure = create_error_msg(status)
        super().__init__(ui_failure, message=message, status=status, origin=origin)

    @staticmethod
    def unknown_url() -> ScrapeError:
        return ScrapeError("Unknown URL path")

    @staticmethod
    def unsupported() -> ScrapeError:
        return ScrapeError("Unsupported")

    @staticmethod
    def no_content(name: str) -> ScrapeError:
        return ScrapeError(204, f"Did not find {name}")

    @staticmethod
    def live_stream(source: object = None) -> ScrapeError:
        msg = "Live streams are not supported"
        if source is not None:
            msg += f" [{source}]"
        return ScrapeError("Live Stream", msg)


class LoginError(_UIError):
    UI_MSG: str = "Failed Login"


class JDownloaderError(_UIError):
    UI_MSG: str = "JDownloader Error"


class InvalidYamlError(_UIError):
    UI_MSG: str = "Invalid YAML"

    def __init__(self, file: Path, e: YAMLError) -> None:
        """This error will be thrown when a yaml config file has invalid values."""
        file = file.resolve()
        msg = f"'{file}' is not a valid YAML file"

        if mark := getattr(e, "problem_mark", None):
            msg += f"\n\nThe error was found in this line: \n {mark}"

        problem = getattr(e, "problem", str(e)).capitalize()
        msg += f"\n\n{problem}\n\nPlease delete the file or fix the errors"
        super().__init__(message=msg, origin=file)


def create_error_msg(error: int | str) -> str:
    if isinstance(error, str):
        return error
    if phrase := HTTP_ERROR_CODES.get(error):
        return f"{error} {phrase}"

    if 300 <= error < 400:
        return f"HTTP Redirection ({error})"
    if 400 <= error < 500:
        return f"HTTP Client Error ({error})"
    if 500 <= error < 600:
        return f"HTTP Server Error ({error})"

    return f"Unknown ({error})"


def get_origin(origin: HasParents | Path | yarl.URL | None = None) -> Path | yarl.URL | None:
    import yarl

    if origin is None:
        return None
    if type(origin) is yarl.URL:
        return origin
    if isinstance(origin, Path):
        return origin
    return origin.parents[0] if origin.parents else None  # pyright: ignore[reportAttributeAccessIssue]


@final
@dataclasses.dataclass(slots=True)
class CDLAppError(RuntimeError):
    ui_error: str
    msg: str = ""
    csv_msg: str = ""

    def __post_init__(self) -> None:
        self.msg = self.msg or self.ui_error
        self.csv_msg = self.csv_msg or self.ui_error
        if self.csv_msg == "Unknown":
            self.csv_msg = "See logs for details"

    @staticmethod
    def from_unknown_exc(e: Exception) -> CDLAppError:
        assert type(e) is not CDLAppError
        e_status = getattr(e, "status", None)
        e_message = getattr(e, "message", None)
        ui_failure = create_error_msg(e_status) if e_status else "Unknown"
        log_msg = _format_error(ui_failure, e_message or f"{type(e).__name__}({e!s})", _notes(e))
        return CDLAppError(ui_failure, log_msg)


class CDLConfigRuntimeErrorsGroup(ExceptionGroup): ...
