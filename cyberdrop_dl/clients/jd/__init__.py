from typing import Any

type Params = list[Any] | tuple[Any, ...]


def prepare_api_json(path: str, json: Params, rid: int) -> dict[str, Any]:
    return {
        "apiVer": 1,
        "url": path,
        "params": json,
        "rid": rid,
    }


def check_resp(data: object) -> None:
    if type(data) is dict and data.get("type") == "BAD_PARAMETERS":
        msg = f"BAD_PARAMETERS ({str(data)[:70]})"
        raise RuntimeError(msg)
