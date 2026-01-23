from typing import Literal

from cyberdrop_dl.cache import Cache


class FakeCache(Cache):
    def get(self, _: str) -> Literal[True]:
        return True

    def save(self, *_) -> None:
        return
