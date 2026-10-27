from __future__ import annotations

import dataclasses
import reprlib
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


def _recursive_repr[T: Callable[[object], str]](fn: T) -> T:
    # Prevent positional only signature guess by type checkers
    return reprlib.recursive_repr()(fn)  # pyright: ignore[reportReturnType]


@_recursive_repr
def vars_repr(self: object) -> str:
    fields = (f"{name}={val!r}" for name, val in vars(self).items())
    return f"<{type(self).__name__}({', '.join(fields)}>"


def _dataclass_repr(field_names: tuple[str, ...]) -> Callable[..., str]:

    @_recursive_repr
    def custom_repr(self: object) -> str:
        fields = (f"{name}={getattr(self, name)!r}" for name in field_names)
        return f"<{type(self).__name__}({', '.join(fields)}>"

    return custom_repr


def dataclass_repr[T](*field_names: str) -> Callable[[type[T]], type[T]]:
    """Create a custom dataclass like `__repr__`

    `__repr__` is created from the values of `vars()` if `field_names` is not provided"""

    def apply(cls: type[T]) -> type[T]:
        if not field_names:
            cls.__repr__ = vars_repr
            assert not dataclasses.is_dataclass(cls)
        else:
            cls.__repr__ = _dataclass_repr(field_names)
            if dataclasses.is_dataclass(cls):
                # This prevents rich from rendering all fields in tracebacks
                for field in dataclasses.fields(cls):
                    if field.name not in field_names:
                        field.repr = False
        return cls

    return apply
