from typing import cast

import pytest

from cyberdrop_dl.clients import download_client
from cyberdrop_dl.data_structures import MediaItem


def _item(fallbacks_: object) -> MediaItem:
    class Item:
        fallbacks = fallbacks_

    return cast("MediaItem", Item)  # pyright: ignore[reportInvalidCast]


def test_fallback_generator_with_none() -> None:
    item = _item(None)
    gen = download_client._fallback_generator(item)
    with pytest.raises(StopIteration):
        _ = gen.send(None)


def test_fallback_generator_with_list() -> None:
    item = _item(["url1", "url2", "url3"])
    gen = download_client._fallback_generator(item)
    assert gen.__next__() == "url1"
    assert gen.__next__() == "url2"
    assert gen.send(12345) == "url3"
    with pytest.raises(StopIteration):
        _ = gen.send(None)


def test_fallback_generator_with_generator() -> None:
    def _fallback_gen(resp: object, retry: object):
        return retry

    item = _item(_fallback_gen)
    gen = download_client._fallback_generator(item)

    assert gen.send(12345) == 1
    assert gen.send(12345) == 2
    with pytest.raises(StopIteration):
        _ = gen.send(None)
