from __future__ import annotations

from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    _P = ParamSpec("_P")
    _R = TypeVar("_R")
    _T = TypeVar("_T")
    import functools
    import inspect
    from collections.abc import Callable

    def copy(target: Callable[_P, _R], /) -> Callable[[Callable[..., _T]], Callable[_P, _T]]:
        def decorator(func: Callable[..., _T]) -> Callable[_P, _T]:
            @functools.wraps(func)
            def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _T:
                return func(*args, **kwargs)

            wrapper.__signature__ = inspect.signature(target).replace(  # pyright: ignore[reportAttributeAccessIssue]
                return_annotation=inspect.signature(func).return_annotation
            )
            return wrapper

        return decorator

else:

    def copy(_target: Callable[_P, _R]) -> Callable[[Callable[..., _T]], Callable[_P, _T]]:
        def decorator(func: Callable[..., _T]) -> Callable[_P, _T]:
            return func

        return decorator
