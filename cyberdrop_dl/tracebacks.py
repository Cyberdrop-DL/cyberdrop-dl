from __future__ import annotations


def patch() -> None:
    from bs4.element import PageElement
    from rich import pretty

    from cyberdrop_dl.utils import truncated_preview

    traverse = pretty.traverse
    if traverse.__name__ == "new_traverse":
        return

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


def install_exception_hook(*, show_locals: bool = False) -> None:
    patch()
    from rich.traceback import install

    _ = install(
        width=None,
        word_wrap=True,
        max_frames=3,
        show_locals=show_locals,
    )
