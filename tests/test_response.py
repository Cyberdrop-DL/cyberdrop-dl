import datetime

from multidict import CIMultiDict, CIMultiDictProxy

from cyberdrop_dl.clients.response import _AIOHTTPResponse
from cyberdrop_dl.url_objects import AbsoluteHttpURL


def make_resp(content_type: str, url: str = "https://example.com") -> _AIOHTTPResponse:
    resp = _AIOHTTPResponse(
        content_type,
        status=200,
        headers=CIMultiDictProxy(CIMultiDict({"content-type": content_type})),
        url=AbsoluteHttpURL(url),
        location=None,
        _resp=None,  # pyright: ignore[reportArgumentType]
    )
    resp.created_at = datetime.datetime.min
    return resp


def test_json_dump_binary_resp() -> None:
    content_type = "application/octet-stream"
    resp = make_resp(content_type)
    json = resp.__json__()
    assert content_type in json["content"]
    assert json == {
        "url": "https://example.com",
        "status_code": 200,
        "created_at": "0001-01-01 00:00:00",
        "response_headers": {
            "content-type": "application/octet-stream",
        },
        "content": "<application/octet-stream payload>",
    }
