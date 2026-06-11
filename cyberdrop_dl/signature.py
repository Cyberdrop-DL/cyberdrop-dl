from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import functools
    import inspect
    from collections.abc import Callable

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
