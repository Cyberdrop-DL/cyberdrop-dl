from __future__ import annotations

import contextlib
import json
import logging
import queue
import sys
from contextvars import ContextVar
from datetime import datetime
from enum import StrEnum
from io import StringIO
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, TypeVar, final

from rich._log_render import LogRender
from rich.console import Console, Group
from rich.logging import RichHandler
from rich.padding import Padding
from rich.text import Text, TextType
from typing_extensions import override

from cyberdrop_dl import env

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable

    from rich.console import ConsoleRenderable


logger = logging.getLogger("cyberdrop_dl")
for noisy_package in ("aiosqlite",):
    logging.getLogger(noisy_package).setLevel(logging.ERROR)

_T = TypeVar("_T")
_USER_NAME = Path.home().name
_DEFAULT_CONSOLE_WIDTH = 240
_MAIN_LOG_LISTENER: ContextVar[QueueListener] = ContextVar("_MAIN_LOG_LISTENER")
_CONSOLE_LOG_LISTENER: ContextVar[QueueListener] = ContextVar("_CONSOLE_LOG_LISTENER")
_LOG_TO_CONSOLE: ContextVar[bool] = ContextVar("LOG_TO_CONSOLE", default=True)

MAIN_LOG_FILE: ContextVar[Path] = ContextVar("MAIN_LOG_FILE")


class HandlerName(StrEnum):
    CONSOLE = "cdl-console"
    MAIN_LOG = "cdl-main-log-file"
    DEBUG_LOG = "cdl-debug-log-file"


class RedactedConsole(Console):
    """Custom console to remove username from logs"""

    @override
    def _render_buffer(self, buffer) -> str:
        return self._redact_message(super()._render_buffer(buffer))

    @classmethod
    def _redact_message(cls, message: object) -> str:
        redacted = str(message)
        for sep in ("\\", "\\\\", "/"):
            as_tail = sep + _USER_NAME
            as_part = _USER_NAME + sep
            redacted = redacted.replace(as_tail, f"{sep}[REDACTED]").replace(as_part, f"[REDACTED]{sep}")
        return redacted


class JsonLogRecord(logging.LogRecord):
    """`dicts` will be logged as json, lazily"""

    @override
    def getMessage(self) -> str:
        msg = str(self._proccess_msg(self.msg))
        if self.args:
            args = tuple(map(self._proccess_msg, self.args))
            if "%" in msg:
                try:
                    return msg % args
                except TypeError as e:
                    if not e.args or "not all arguments converted" in e.args[0]:
                        raise

            return msg.format(*args)

        return msg

    @staticmethod
    def _proccess_msg(obj: object) -> object:
        if callable(dump := getattr(obj, "model_dump_json", None)):
            return dump(indent=2, ensure_ascii=False)
        if callable(dump := getattr(obj, "__json__", None)):
            return json.dumps(dump(), indent=2, ensure_ascii=False, default=str)
        if isinstance(obj, dict):
            return json.dumps(obj, indent=2, ensure_ascii=False, default=str)
        return obj


logging.setLogRecordFactory(JsonLogRecord)


class CDLFormater(logging.Formatter):
    _CDL_FORMAT: ClassVar[logging.PercentStyle] = logging.PercentStyle("%(message)s")

    def formatMessage(self, record: logging.LogRecord) -> str:  # noqa: N802
        if record.name.startswith("cyberdrop_dl"):
            return self._CDL_FORMAT.format(record)

        return self._style.format(record)


class LogHandler(RichHandler):
    """Rich Handler with default settings, custom log render to remove padding in files and `color` extra"""

    def __init__(
        self,
        level: int = logging.DEBUG,
        console: Console | None = None,
        *,
        show_time: bool,
    ) -> None:
        super().__init__(
            level,
            console,
            show_time=show_time,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            tracebacks_max_frames=30,
            locals_max_string=_DEFAULT_CONSOLE_WIDTH,
            locals_max_length=20,
            show_path=False,
            show_level=True,
        )
        if show_time:
            self._log_render = NoPaddingLogRender(
                show_time=show_time,
                show_level=True,
                show_path=False,
                level_width=10,
                time_format=lambda dt: Text(f"[{dt.isoformat(sep=' ', timespec='milliseconds')}]", style="log.time"),
            )

        self.setFormatter(CDLFormater("[%(name)s]: %(message)s"))

    @override
    def render_message(self, record: logging.LogRecord, message: str) -> ConsoleRenderable:
        """This is the same as the base class, just added the `color` parsing from the extras"""
        use_markup = bool(getattr(record, "markup", self.markup))
        color = getattr(record, "color", "")
        message_text = Text.from_markup(message, style=color) if use_markup else Text(message, style=color)

        highlighter = getattr(record, "highlighter", self.highlighter)
        if highlighter:
            message_text = highlighter(message_text)

        if self.keywords is None:
            self.keywords = self.KEYWORDS

        if self.keywords:
            _ = message_text.highlight_words(self.keywords, "logging.keyword")

        return message_text


class BareQueueHandler(QueueHandler):
    """Sends the log record to the queue as is.

    The base class formats the record by merging the message and arguments.
    It also removes all other attributes of the record, just in case they have not pickleable objects.

    This made tracebacks render improperly because when the rich handler picks the log record from the queue, it has no traceback.
    The original traceback was being formatted as normal text and included as part of the message.

    We never log from other processes so we do not need that safety check
    """

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        return record


@contextlib.contextmanager
def _threaded_logger(
    log_handler: logging.Handler,
    *,
    context_var: ContextVar[QueueListener] | None = None,
) -> Generator[BareQueueHandler]:
    """Context-manager to process logs from this handler in another thread"""
    q: queue.Queue[logging.LogRecord] = queue.Queue()
    q_handler: BareQueueHandler = BareQueueHandler(q)
    q_listener: QueueListener = QueueListener(q, log_handler, respect_handler_level=True)
    q_listener.start()

    with _enter_context(context_var, q_listener) if context_var else contextlib.nullcontext():
        logging.getLogger().addHandler(q_handler)
        try:
            yield q_handler
        finally:
            logging.getLogger().removeHandler(q_handler)
            try:
                q_handler.close()
            finally:
                q_listener.stop()
                for handler in q_listener.handlers[:]:
                    handler.close()


@contextlib.contextmanager
def _enter_context(context_var: ContextVar[_T], value: _T) -> Generator[None]:
    token = context_var.set(value)
    try:
        yield
    finally:
        context_var.reset(token)


@final
class NoPaddingLogRender(LogRender):
    _cdl_padding: int = 0

    def __call__(  # type: ignore[reportIncompatibleMethodOverride]  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        console: Console,
        renderables: Iterable[ConsoleRenderable],
        log_time: datetime | None = None,
        time_format: str | Callable[[datetime], Text] | None = None,
        level: TextType = "",
        path: str | None = None,
        line_no: int | None = None,
        link_path: str | None = None,
    ):
        output = Text(no_wrap=True)
        if self.show_time:
            log_time = log_time or console.get_datetime()
            time_format = time_format or self.time_format
            log_time_display = (
                time_format(log_time)
                if callable(time_format)
                else Text(log_time.strftime(time_format), style="log.time")
            )
            if log_time_display == self._last_time and self.omit_repeated_times:
                output.append(" " * len(log_time_display), style="log.time").pad_right(1)
            else:
                output.append_text(log_time_display).pad_right(1)
                self._last_time = log_time_display

        if self.show_level:
            output.append(level).pad_right(1)

        if not self._cdl_padding:
            self._cdl_padding = console.measure(output).maximum

        if self.show_path and path:
            path_text = Text(style="log.path")
            _ = path_text.append(path, style=f"link file://{link_path}" if link_path else "")
            if line_no:
                _ = path_text.append(":")
                _ = path_text.append(
                    f"{line_no}",
                    style=f"link file://{link_path}#{line_no}" if link_path else "",
                )
            output.append_text(path_text).pad_right(1)

        padded_lines: list[ConsoleRenderable] = []

        for renderable in renderables:
            if isinstance(renderable, Text):
                renderable = _indent_text(renderable, console, self._cdl_padding)
                renderable.stylize("log.message")
                _ = output.append_text(renderable)
                continue

            padded_lines.append(Padding(renderable, (0, 0, 0, self._cdl_padding), expand=False))

        return Group(output, *padded_lines)


def _indent_text(text: Text, console: Console, indent: int) -> Text:
    """Indents each line of a Text object except the first one."""
    padding = Text("\n" + (" " * indent))
    new_text = Text()
    first_line, *rest = text.wrap(console, width=console.width - indent)
    for line in rest:
        line.rstrip()
        _ = new_text.append_text(padding + line)
    first_line.rstrip()
    return first_line.append_text(new_text)


def log_spacer(char: str = "-") -> None:
    logger.info(char * 30, stacklevel=2)


def _get_handler(name: str) -> logging.Handler:
    for handler in logging.getLogger().handlers:
        if handler.get_name() == name:
            return handler
    raise LookupError(name)


def set_console_level(level: int) -> None:
    _get_handler(HandlerName.CONSOLE).setLevel(level)


@contextlib.contextmanager
def setup_console_logging() -> Generator[None]:
    handler = LogHandler(logging.DEBUG, show_time=False)
    logging.getLogger().setLevel(logging.DEBUG)
    try:
        with _threaded_logger(handler, context_var=_CONSOLE_LOG_LISTENER) as q_handler:
            q_handler.set_name(HandlerName.CONSOLE)
            q_handler.addFilter(lambda _: _LOG_TO_CONSOLE.get())
            yield
    finally:
        if "pytest" not in sys.modules:
            # Re add it as a normal handler to make sure uncatched exceptions show up
            logging.getLogger().addHandler(handler)


@contextlib.contextmanager
def setup_file_logging(file: Path, /, *, level: int = logging.DEBUG) -> Generator[None]:
    file.parent.mkdir(parents=True, exist_ok=True)
    import mega

    with (
        _setup_debug_logger() as debug_log_file,
        file.open("w", encoding="utf8") as fp,
        _enter_context(MAIN_LOG_FILE, file),
        _enter_context(mega.LOG_HTTP_TRAFFIC, True),
        _enter_context(mega.LOG_FILE_PROGRESS, False),
        _threaded_logger(
            log_handler=LogHandler(
                level=logging.DEBUG,
                show_time=True,
                console=RedactedConsole(file=fp, width=_DEFAULT_CONSOLE_WIDTH * 2),
            ),
            context_var=_MAIN_LOG_LISTENER,
        ) as handler,
    ):
        handler.setLevel(level)
        handler.set_name(HandlerName.MAIN_LOG)
        logger.info(f"Debug log file: {debug_log_file}")
        try:
            yield
        except Exception:
            with _enter_context(_LOG_TO_CONSOLE, False):
                logger.critical("Unrecoverable error", exc_info=True)
            raise


@contextlib.contextmanager
def _setup_debug_logger() -> Generator[Path | None]:
    if not env.DEBUG_MODE:
        yield
        return

    debug_log_file = Path(__file__).parent.parent / "cyberdrop_dl_debug.log"

    if env.DEBUG_LOG_FOLDER:
        debug_log_folder = Path(env.DEBUG_LOG_FOLDER).expanduser()

        if not debug_log_folder.exists():
            msg = f"Value of env var 'CDL_DEBUG_LOG_FOLDER' is invalid. Folder '{debug_log_folder}' does not exists"
            raise FileNotFoundError(None, msg, env.DEBUG_LOG_FOLDER)

        if not debug_log_folder.is_dir():
            msg = (
                f"Value of env var 'CDL_DEBUG_LOG_FOLDER' is invalid. Folder '{debug_log_folder}' should a be directory"
            )
            raise NotADirectoryError(None, msg, env.DEBUG_LOG_FOLDER)

        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_log_file = debug_log_folder / f"cyberdrop_dl_debug_{now}.log"

    debug_log_file = debug_log_file.resolve().absolute()

    with (
        debug_log_file.open("w", encoding="utf8") as fp,
        _threaded_logger(
            LogHandler(
                level=logging.NOTSET + 1,
                console=Console(file=fp, width=_DEFAULT_CONSOLE_WIDTH * 2),
                show_time=True,
            ),
        ) as handler,
    ):
        handler.set_name(HandlerName.DEBUG_LOG)
        yield debug_log_file


@contextlib.contextmanager
def capture_logs() -> Generator[StringIO]:
    in_memory_handler = logging.StreamHandler(file := StringIO())
    logging.getLogger().addHandler(in_memory_handler)
    try:
        yield file
    finally:
        logging.getLogger().removeHandler(in_memory_handler)


def export_logs(*, size_limit: float | None = None) -> bytes:
    flush_logs()
    log_file = MAIN_LOG_FILE.get()
    if size_limit and log_file.stat().st_size > size_limit:
        raise RuntimeError(f"Logs file '{log_file}' is too big. Max size expected: {size_limit}")
    return log_file.read_bytes()


def flush_logs() -> None:
    """Wait until every record that is currently queued has been written to disk"""
    listener = _MAIN_LOG_LISTENER.get()
    listener.stop()
    listener.start()


def disable_console_logging():
    try:
        listener = _CONSOLE_LOG_LISTENER.get()
    except LookupError:
        pass
    else:
        listener.stop()
        listener.start()
    return _enter_context(_LOG_TO_CONSOLE, False)


@contextlib.contextmanager
def borrow_logger(name: str, level: int = logging.INFO) -> Generator[None]:
    """Context manager to temporarily add our log handlers to a third party logger"""
    _3p_logger = logging.getLogger(name)
    og_level = _3p_logger.level
    _3p_logger.setLevel(level)
    try:
        yield
    finally:
        _3p_logger.setLevel(og_level)
