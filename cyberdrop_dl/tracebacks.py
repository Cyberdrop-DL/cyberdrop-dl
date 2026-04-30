from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from rich.pretty import Node

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
        except Exception:
            return False

    def new_traverse(obj, *args, **kwargs):
        if is_page_element(obj):
            try:
                value_repr = truncated_preview(repr(obj))
            except Exception as error:
                value_repr = f"<repr-error {str(error)!r}>"

            return pretty.Node(value_repr=value_repr, last=False)

        return traverse(obj, *args, **kwargs)

    pretty.traverse = new_traverse
    _original_traverse = traverse


def install_exception_hook(*, show_locals: bool = False) -> None:
    patch()
    from rich.traceback import install

    _ = install(
        width=None,
        word_wrap=True,
        max_frames=3,
        show_locals=show_locals,
    )
