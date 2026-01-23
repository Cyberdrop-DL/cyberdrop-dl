from typing import Literal

from cyberdrop_dl.managers.cache_manager import Cache


class FakeCacheManager(Cache):
    def get(self, _: str) -> Literal[True]:
        return True

    def save(self, *_) -> None:
        return
