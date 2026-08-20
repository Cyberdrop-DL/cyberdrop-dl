from __future__ import annotations

from typing import Any


class nested_itemgetter:  # noqa: N801
    def __init__(self, key: str, *keys: str) -> None:
        self.keys: tuple[str, ...] = key, *keys

    def __call__(self, obj: Any) -> Any:
        path: list[str] = []
        for key in self.keys:
            path.append(key)
            try:
                obj = obj[key]
            except (KeyError, TypeError):
                raise KeyError(str(path)) from None

        return obj

    def __repr__(self) -> str:
        return f"{type(self).__name__}({', '.join(map(repr, self.keys))})"


class nested_itemsetter:  # noqa: N801
    def __init__(self, key: str, *keys: str) -> None:
        self.keys: tuple[str, ...] = key, *keys

    __repr__ = nested_itemgetter.__repr__

    def __call__(self, obj: Any, value: Any) -> Any:
        path: list[str] = []
        *keys, last = self.keys
        for key in keys:
            path.append(key)
            try:
                obj = obj[key]
            except KeyError:
                obj[key] = {}
                obj = obj[key]

        obj[last] = value
