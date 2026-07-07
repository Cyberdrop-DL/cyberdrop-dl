from __future__ import annotations

import reprlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import functools
    import inspect
    from collections.abc import Callable, Generator

    def copy[**P, T, R](target: Callable[P, R], /) -> Callable[[Callable[..., T]], Callable[P, T]]:
        def decorator(func: Callable[..., T]) -> Callable[P, T]:
            @functools.wraps(func)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                return func(*args, **kwargs)

            wrapper.__signature__ = inspect.signature(target).replace(  # pyright: ignore[reportAttributeAccessIssue]
                return_annotation=inspect.signature(func).return_annotation
            )
            return wrapper

        return decorator

else:

    def copy[**P, T, R](_target: Callable[P, R]) -> Callable[[Callable[..., T]], Callable[P, T]]:
        def decorator(func: Callable[..., T]) -> Callable[P, T]:
            return func

        return decorator


def repr_fields(*fields: tuple[str, Any]) -> Generator[str]:
    for name, value in fields:
        yield f"{name}={value!r}"


def simple_repr(*names: str) -> Callable[..., str]:

    @reprlib.recursive_repr()
    def repr_(self: object) -> str:
        fields = ((name, getattr(self, name)) for name in names)
        return f"<{type(self).__name__}({', '.join(repr_fields(*fields))}>"

    return repr_
