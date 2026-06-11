from __future__ import annotations

import re
from typing import TYPE_CHECKING

from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import is_absolute_http_url, remove_trailing_slash

if TYPE_CHECKING:
    from collections.abc import Iterable

    from cyberdrop_dl.crawlers.crawler import Crawler


def create_crawlers[CrawlerT: Crawler](
    urls: Iterable[str] | Iterable[AbsoluteHttpURL], base_crawler: type[CrawlerT]
) -> set[type[CrawlerT]]:
    """Creates new subclasses of the base crawler from the urls"""
    return {_create_subclass(url, base_crawler) for url in urls}


def _create_subclass[CrawlerT: Crawler](url: AbsoluteHttpURL | str, base_class: type[CrawlerT]) -> type[CrawlerT]:
    url = AbsoluteHttpURL(url)
    assert is_absolute_http_url(url)
    primary_url = remove_trailing_slash(url)
    domain = primary_url.host.removeprefix("www.")
    class_name = _make_crawler_name(domain)
    class_attributes = {
        "PRIMARY_URL": primary_url,
        "DOMAIN": domain,
        "SUPPORTED_DOMAINS": (),
        "FOLDER_DOMAIN": "",
    }
    return type(class_name, (base_class,), class_attributes)  # pyright: ignore[reportReturnType]


def _make_crawler_name(input_string: str) -> str:
    clean_string = re.sub(r"[^a-zA-Z0-9]+", " ", input_string).strip()
    cap_name = clean_string.title().replace(" ", "")
    msg = f"Can not generate a valid class name from {input_string}. Needs to be defined as a concrete class"
    assert cap_name, msg
    assert cap_name.isalnum(), msg
    if cap_name[0].isdigit():
        cap_name = "_" + cap_name
    return f"{cap_name}Crawler"
