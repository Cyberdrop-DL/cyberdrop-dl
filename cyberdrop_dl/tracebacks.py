from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

    from rich.pretty import Node
    from rich.traceback import Traceback

_original_traverse = None


def original_traverse() -> Callable[..., Node]:
    patch()
    assert callable(_original_traverse)
    return _original_traverse


def patch() -> None:
    global _original_traverse
    if _original_traverse is not None:
        return

    from bs4.element import PageElement
    from rich import pretty

    from cyberdrop_dl.utils import truncated_preview

    traverse = pretty.traverse

    def is_page_element(obj: object) -> bool:
        try:
            return isinstance(obj, PageElement)
        except Exception:  # noqa: BLE001
            return False

    def new_traverse(obj, *args: Any, **kwargs: Any) -> pretty.Node:
        if is_page_element(obj):
            try:
                value_repr = truncated_preview(repr(obj))
            except Exception as error:  # noqa: BLE001
                value_repr = f"<repr-error {str(error)!r}>"

            return pretty.Node(value_repr=value_repr, last=False)

        return traverse(obj, *args, **kwargs)

    pretty.traverse, _original_traverse = new_traverse, traverse


def install_exception_hook(*, show_locals: bool = False) -> None:
    patch()
    from rich.traceback import install

    _ = install(
        width=None,
        word_wrap=True,
        max_frames=30,
        show_locals=show_locals,
    )


def from_exception(exc: Exception, *, chain_traceback: bool = False) -> Traceback:
    from rich.traceback import Traceback

    return Traceback.from_exception(type(exc), exc, None if not chain_traceback else exc.__traceback__)


def strip_frames(tb: TracebackType | None) -> TracebackType | None:
    "Similar to pytest, hide anything with __tracebackhide__"
    if tb is None:
        return None

    for ns in (tb.tb_frame.f_locals, tb.tb_frame.f_globals):
        if ns.get("__tracebackhide__"):
            return strip_frames(tb.tb_next)

    tb.tb_next = strip_frames(tb.tb_next)
    return tb


def strip_frames_from_exc(exc: BaseException | None) -> None:
    if exc is None:
        return

    exc.__traceback__ = strip_frames(exc.__traceback__)

    strip_frames_from_exc(exc.__cause__)
    strip_frames_from_exc(exc.__context__)
