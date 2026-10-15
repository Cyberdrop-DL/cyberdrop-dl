from typing import Any

import pytest

from cyberdrop_dl.crawlers import yandex_disk


def test_raise_for_wrong_sk() -> None:
    with pytest.raises(yandex_disk._WrongSkError) as exc_info:
        yandex_disk._raise_for_wrong_sk({"error": True, "wrongSk": True, "newSk": "y2"})
    assert exc_info.value.new_sk == "y2"


@pytest.mark.parametrize(
    "json_resp",
    [
        {"error": True},
        {"error": True, "wrongSk": True},
        {"error": False, "statusCode": 200, "data": {"url": "https://downloader.disk.yandex.com/disk/x"}},
        ["not", "a", "dict"],
    ],
)
def test_raise_for_wrong_sk_ignores_other_responses(json_resp: Any) -> None:
    yandex_disk._raise_for_wrong_sk(json_resp)
