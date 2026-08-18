from typing import Any

import yarl

type Params = dict[str, Any] | list[Any] | tuple[Any, ...]


def prepare_api_json(url: yarl.URL, json: Params, rid: int) -> dict[str, Any]:
    return {
        "apiVer": 1,
        "url": url.path,
        "params": [json] if type(json) is dict else json,
        "rid": rid,
    }


def check_resp(data: object) -> None:
    if type(data) is dict and data.get("type") == "BAD_PARAMETERS":
        msg = f"BAD_PARAMETERS ({str(data)[:40]})"
        raise RuntimeError(msg)
