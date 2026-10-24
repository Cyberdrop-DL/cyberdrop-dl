from __future__ import annotations

from typing import TYPE_CHECKING

from cyberdrop_dl.utils import parse_url

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import AbsoluteHttpURL


def full_res_img(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    match url.host.rsplit(".", 2):
        case [subdomain, "userapi", "com"]:
            match url.parts[1:]:
                case ["impf" | "impg", *rest]:
                    return url.origin().joinpath(*rest).with_host("pp.userapi.com")
                case ["s", "v1", *_]:
                    return url.update_query(cs="99999x99999")
                case _:
                    if subdomain.startswith(("sun", "psv")):
                        return url.with_host("pp.userapi.com")
                    return url
        case _:
            return url


def try_parse_url(value: object) -> AbsoluteHttpURL | None:
    if value and type(value) is str and value.startswith(("//", "http")):
        return parse_url(value)
