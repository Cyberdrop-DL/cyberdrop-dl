from __future__ import annotations

from multidict import CIMultiDict

from cyberdrop_dl.clients.request import Request
from cyberdrop_dl.url_objects import AbsoluteHttpURL


def test_get_is_promoted_to_post_when_data_present() -> None:
    req = Request(url=AbsoluteHttpURL("https://example.com"), method="GET", data=b"payload")
    assert req.method == "POST"


def test_get_is_promoted_to_post_when_json_present() -> None:
    req = Request(url=AbsoluteHttpURL("https://example.com"), method="GET", json={"key": "value"})
    assert req.method == "POST"


def test_json_omits_empty_headers() -> None:
    req = Request(
        url=AbsoluteHttpURL("https://example.com"),
        method="GET",
        headers=CIMultiDict(),
    )
    assert "headers" not in req.__json__()


def test_json_method_returns_expected_dict() -> None:
    req = Request(
        url=AbsoluteHttpURL("https://example.com"),
        method="GET",
        headers=CIMultiDict([("Accept", "application/json")]),
        impersonate="firefox",
        data=None,
        json={"foo": "bar"},
        params={},
    )
    expected = {
        "url": "https://example.com",
        "headers": {"Accept": "application/json"},
        "impersonate": "firefox",
        "json": {"foo": "bar"},
    }
    assert req.__json__() == expected
