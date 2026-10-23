from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cyberdrop_dl.url_objects import AbsoluteHttpURL


def unblur(url: AbsoluteHttpURL) -> AbsoluteHttpURL:
    clean_path = url.path.replace("/impf/", "/").replace("/impg/", "/")
    if clean_path != url.path:
        return url.with_path(clean_path, keep_query=False)
    return url
